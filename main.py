#!/usr/bin/env python3
"""Remote server for the `mclip` apps"""

import sqlite3
import json
import logging
import re
import os
import sys
from uuid import uuid4
from datetime import datetime
from base64 import b64encode, b64decode

import uvicorn
from fastapi import FastAPI, HTTPException, Response, Request, Query
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

class ColoredFormatter(logging.Formatter):
    """Formatter matching FastAPI logs"""
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }

    def format(self, record):
        record.levelname = self.COLORS[record.levelname] + \
            record.levelname + '\033[0m'
        return super().format(record)

# Configure logger to match FastAPI's format with colors
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter("%(levelname)s:     %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger(__name__)

users: dict[str, str] = {}


def db_exec(query: str, username: str, *args) -> list[dict]:
    """Execute a query in data/<username>.db"""
    with sqlite3.connect(f"data/{username}.db", autocommit=True) as conn:
        conn.execute("PRAGMA busy_timeout = 2000") # wait up to 2s if database is locked
        conn.row_factory = sqlite3.Row
        fetched = None
        try:
            fetched = conn.execute(query, args).fetchall()
            return [dict(row) for row in fetched] if fetched else []
        except Exception as e:
            log.error("Database operatrion failed for %s: %s", username, e)
            raise HTTPException(500, "Something is really wrong") from e


def init_db(username: str) -> None:
    """Initialize a database for user"""
    db_exec("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            content BLOB NOT NULL
        )""", username)


def get_username(request: Request) -> str:
    """
    Validate the credentials and return username.
    Raises **HTTP 401** if malformed or invalid password.
    """
    credentials = request.headers.get("Authorization")
    try:
        if credentials is None or not credentials.startswith("Basic "):
            raise RuntimeError
        credentials = b64decode(credentials[6:], validate=True).decode()
    except Exception as e:
        raise HTTPException(401, "Invalid credentials") from e

    if ":" not in credentials:
        raise HTTPException(401, "Invalid credentials")
    username, password = credentials.split(":", 1)

    if users.get(username) != password:
        raise HTTPException(401, "Invalid credentials")

    return username


def validate_content_type(request: Request, starts: str) -> None:
    """Raise **HTTP 415** if Content-Type doesn't start with `starts`"""
    content_type = request.headers.get("Content-Type")
    if content_type is None or not content_type.startswith(starts):
        raise HTTPException(415, "Invalid Content-Type header")


def validate_item_existence(username: str, uuid: str) -> None:
    """Raise **HTTP 404** if user has no item with given id."""
    with sqlite3.connect(f"data/{username}.db") as conn:
        conn.execute("PRAGMA busy_timeout = 2000") # wait up to 2s if database is locked
        try:
            if not conn.execute(
                "SELECT EXISTS (SELECT 1 FROM items WHERE id = ?)", uuid
            ).fetchone()[0]:
                raise HTTPException(404, "No item with provided ID")
        except Exception as e:
            log.error("Item existence check failed for %s: %s", username, e)
            raise HTTPException(500, "Something is really wrong") from e


app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware)
limiter = Limiter(key_func=get_remote_address)


@app.head("/api")
@limiter.limit("10/minute")
async def root(request: Request): # pylint: disable=unused-argument
    """Status check endpoint"""
    return Response(status_code=200)


@app.get("/api/items")
@limiter.limit("10/minute")
async def list_items(
    request: Request,
    type_filter: str | None = Query(None), name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
    altered_after: str | None = Query(None), include_content: bool = Query(False)
    ):
    """
    Execute SELECT query with url-encoded parameters. Return result in application/json.
    """
    username = get_username(request)

    if type_filter is not None and type_filter not in ("text", "file"):
        raise HTTPException(400, "Invalid type parameter. Must be 'text' or 'file'.")

    if altered_after is not None:
        try:
            datetime.strptime(altered_after, "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            raise HTTPException(400, "Invalid altered_after. Expected YYYY-MM-DD HH:MM:SS.") from e

    content_expr = "content"
    if not include_content:
        content_expr = "CASE WHEN type = 'text' THEN substr(content, 1, 180) ELSE NULL END"

    query = f"SELECT id, timestamp, type, name, {content_expr} AS content FROM items"
    where_clauses = []
    params = []

    if type_filter is not None:
        where_clauses.append("type = ?")
        params.append(type_filter)
    if name is not None:
        where_clauses.append("name LIKE ? ESCAPE '\\'")
        params.append(name)
    if altered_after is not None:
        where_clauses.append("timestamp >= ?")
        params.append(altered_after)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    items = db_exec(query, username, *params, limit, offset)
    try:
        for item in items:
            if item["content"] is None:
                item["content"] = ""
            else:
                item["content"] = b64encode(item["content"]).decode()
    except Exception as e:
        raise HTTPException(500, "Internal server error") from e

    return Response(content=json.dumps(items), media_type="application/json", status_code=200)

@app.post("/api/items")
@limiter.limit("10/minute")
async def create_item(request: Request):
    """Create a new item with provided fields. Return generated ID."""
    validate_content_type(request, "application/json")
    username = get_username(request)

    try:
        body: dict[str, str] = await request.json()
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(400, "Malformed json") from e

    if not {"type", "name", "content"}.issubset(body):
        raise HTTPException(400, "Missing fields")

    if body["type"] not in {"text", "file"}:
        raise HTTPException(422, "Invalid item type")

    try:
        content = b64decode(body["content"])
    except Exception as e:
        raise HTTPException(422, "Content is not base64") from e

    uuid = str(uuid4())

    db_exec("INSERT INTO items (id, type, name, content) VALUES (?, ?, ?, ?)",
            username, uuid, body["type"], body["name"], content)
    return Response(content=uuid, status_code=200)

@app.patch("/api/items/{uuid}")
@limiter.limit("45/minute")
async def alter_item(request: Request, uuid: str):
    """Alter item with provided id. Change name, content or both."""
    validate_content_type(request, "application/json")
    username = get_username(request)

    try:
        body: dict[str, str] = await request.json()
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(400, "Malformed json") from e

    fields = {}
    if "name" in body:
        fields["name"] = body["name"]
    if "content" in body:
        fields["content"] = body["content"]

    if not fields:
        raise HTTPException(400, "No changes specified")

    validate_item_existence(username, uuid)
    set_clause = ", ".join(f"{key} = ?" for key in fields)

    db_exec(f"UPDATE items SET timestamp = CURRENT_TIMESTAMP, {set_clause} WHERE id = ?",
            username, *fields.values(), uuid)
    return Response(status_code=204)

@app.delete("/api/items/{uuid}")
@limiter.limit("30/minute")
async def delete_item(request: Request, uuid: str):
    """Delete item with provided id."""
    username = get_username(request)
    validate_item_existence(username, uuid)

    db_exec("DELETE FROM items WHERE id = ?", username, uuid)
    return Response(status_code=204)


@app.head("/api/account/{username}")
@limiter.limit("50/hour")
async def check_name(request: Request, name: str): # pylint: disable=unused-argument
    """Endpoint for checking name availability."""
    if name in users:
        return Response(status_code=409)
    else:
        return Response(status_code=200)


@app.post("/api/account")
@limiter.limit("3/hour")
async def register(request: Request):
    """Create a new account with given name and password"""
    auth = request.headers.get("Authorization")
    if auth is None or not auth.startswith("Basic "):
        raise HTTPException(400, "Invalid Authtorization header")

    try:
        auth = b64decode(auth[6:]).decode("utf-8")
        if auth.find(":") == -1:
            raise RuntimeError
    except Exception as e:
        raise HTTPException(400, "Invalid Authtorization header") from e

    if re.match(r"^[a-zA-Z0-9_.-]{3,100}:[a-zA-Z0-9_.-]{3,100}$", auth) is None:
        raise HTTPException(422, "Unacceptable name or password")

    username, password = auth.split(":", 1)

    if users.get(username) is not None:
        raise HTTPException(409, "Name not available")

    users[username] = password
    init_db(username)
    return Response(status_code=201)


@app.patch("/api/account")
@limiter.limit("3/hour")
async def change_password(request: Request):
    """Change user's password"""
    validate_content_type(request, "text/plain")
    username = get_username(request)
    password = (await request.body()).decode()

    try:
        assert re.match(r"^[a-zA-Z0-9_.-]{3,100}$", password)
    except Exception as e:
        raise HTTPException(422, "New password is unacceptable") from e

    users[username] = password
    return Response(status_code=204)


@app.delete("/api/account")
@limiter.limit("2/hour")
async def delete_account(request: Request):
    """Delete an account"""
    username = get_username(request)

    users.pop(username)
    os.remove(f"data/{username}.db")

    return Response(status_code=204)


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    try:
        with open("data/users.txt", "r", encoding="utf-8") as f:
            raw_lines = [line.strip("\n") for line in f if line.strip()]
        for line in raw_lines:
            if ":" not in line:
                log.warning("Malformed line (no colon): %s", line)
                continue
            maybe_name, hopefully_password = line.split(":", 1)
            users[maybe_name] = hopefully_password
    except FileNotFoundError:
        log.warning("data/users.txt doesn't exist. New server?")

    if len(sys.argv) == 1:
        log.fatal("Domain not specified (`http` to run withour encryption).")
        sys.exit(1)
    if len(sys.argv) > 2:
        log.info("Extra arguments are ignored")

    domain = sys.argv[1]
    if domain == "http":
        uvicorn.run(
            app, host="0.0.0.0", port=80,
            timeout_keep_alive=20
        )
    else:
        if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
            log.fatal("SSL certificate is required. See README.md.")
        uvicorn.run(
            app, host="0.0.0.0", port=443,
            ssl_certfile=f"/etc/letsencrypt/live/{domain}/fullchain.pem",
            ssl_keyfile=f"/etc/letsencrypt/live/{domain}/privkey.pem",
            timeout_keep_alive=20
        )

    with open("data/users.txt", "w", encoding="utf-8") as f:
        for user, hashed in users.items():
            f.write(f"{user}:{hashed}\n")
