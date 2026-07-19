"""Remote server for the `mclip` apps"""

import sqlite3
import json
import os
import logging
import sys
import re
from base64 import b64encode, b64decode

import uvicorn
from fastapi import FastAPI, HTTPException, Response, Request
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

# Configure logger to match FastAPI"s format with colors
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter("%(levelname)s:     %(message)s"))
logging.basicConfig( level=logging.INFO, handlers=[handler] )
log = logging.getLogger()

def db_exec(query: str, username: str) -> list[dict]:
    """Execute a query in data/<username>.db"""
    conn = sqlite3.connect(f"data/{username}.db", autocommit=True)
    conn.row_factory = sqlite3.Row
    with conn:
        fetched = None
        for _ in range(0, 3):
            try:
                fetched = conn.execute(query).fetchall()
            except sqlite3.OperationalError:
                continue
        return [dict(row) for row in fetched] if fetched else []


def init_db(username: str) -> None:
    """Initialize a database for user"""
    db_exec("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            content BLOB NOT NULL
        )""", username)
    
def parse_credentials(request: Request) -> str:
    """Return the credentials pair. Raise **HTTP 401** if malformed."""
    credentials = request.headers.get("Authorization")
    
    try:
        if credentials is None or not credentials.startswith("Basic "):
            raise RuntimeError
        credentials = b64decode(credentials[6:], validate=True).decode()
        return credentials
    except Exception as e:
        raise HTTPException(401, "Invalid credentials") from e

def validate_query(query: str) -> None:
    """Raise **HTTP 422** if query is not safe for execution"""
    query = query.upper() # <- "create" == "CREATE"
    blacklist = [
        "DROP", "ALTER", "CREATE", "EXPLAIN", "UPSERT", 
        "ATTACH", "DETACH", "PRAGMA", "READFILE"
    ]
    for banned in blacklist:
        if banned in query:
            raise HTTPException(422, "Query contains forbidden elements")

def validate_credentials(credentials: str) -> None:
    """Raise **HTTP 401** if credentials are invalid"""
    with open("data/users.txt", "r", encoding="utf-8") as users:
        for user in users:
            if user == credentials:
                return
    raise HTTPException(401, "Invalid credentials")

def validate_content_type(request: Request, starts: str) -> None:
    """Raise **HTTP 415** if Content-Type doesn't start with `starts`"""
    content_type = request.headers.get("Content-Type")
    if content_type is None or not content_type.startswith(starts):
        raise HTTPException(415, "Invalid Content-Type header")


limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

@app.head("/api")
@limiter.limit("10/minute")
async def root(request: Request): # pylint: disable=unused-argument
    """Status check endpoint"""
    return Response(204)

@app.post("/api/query")
@limiter.limit("90/minute")
async def api(request: Request):
    """Execute a text/plain SQL query , return application/json result"""
    validate_content_type(request, "text/plain")
    credentials = parse_credentials(request)
    validate_credentials(credentials)

    try:
        content = (await request.body()).decode()
    except UnicodeDecodeError as e:
        raise HTTPException(400, "Malformed query") from e
    validate_query(content)

    try:
        result = db_exec(content, credentials.split(":")[0])
        # Convert binary to base64
        for row in result:
            if "content" in row.keys():
                row["content"] = b64encode(row["content"]).decode()
        return Response(media_type="application/json", content=json.dumps(result))
    except sqlite3.Error as e:
        raise HTTPException(400, "Malformed query") from e
    except Exception as e:
        raise HTTPException(500, "Internal server error") from e

@app.post("/api/account")
@limiter.limit("4/hour")
async def register(request: Request):
    """Create a new user with given name and password"""
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

    name = auth.split(":")[0]
    with open("data/users.txt", "a+", encoding="utf-8") as users:
        users.seek(0, os.SEEK_SET)
        for user in users:
            if name == user.split(":")[0]:
                raise HTTPException(409, "Name not available")
        users.write(auth + "\n")
    init_db(name)

    return Response("Success", 201)

@app.patch("/api/account")
@limiter.limit("4/hour")
async def change_password(request: Request):
    """Change user's password"""
    validate_content_type(request, "text/plain")
    credentials = parse_credentials(request)

    try:
        assert re.match(r"^[a-zA-Z0-9_.-]{3,100}$", (await request.body()).decode())
    except Exception as e:
        raise HTTPException(422, "New password in unacceptable") from e

    lines = []
    updated = False
    log.error(credentials)
    with open("data/users.txt", "r", encoding="utf-8") as users:
        for user in users:
            log.error(user)
            if credentials == user.strip("\n "):
                user = user.split(":")[0] + ":" + (await request.body()).decode("utf-8")
                updated = True
            lines.append(user)

    if not updated:
        raise HTTPException(401, "Invalid credentials")

    with open("data/users.txt", "w", encoding="utf-8") as users:
        users.writelines(lines)

    return Response(204)

# ------- MAIN -------

app.add_middleware(GZipMiddleware)

os.makedirs("data", exist_ok=True)
with open("data/users.txt", "a+", encoding="utf-8") as file:
    file.seek(0, os.SEEK_SET)
    for line in file:
        init_db(line.split(":")[0])

if len(sys.argv) == 1:
    log.fatal("Protocol not specified (http/https).")
    exit(1)

if sys.argv[1] == "http":
    if len(sys.argv) > 2:
        log.info("Extra arguments are ignored")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
        timeout_keep_alive=10
    )

elif sys.argv[1] == "https":
    if len(sys.argv) == 2:
        log.fatal("Domain not specified.")
        exit(1)
    if len(sys.argv) > 3:
        log.info("Extra arguments are ignored.")

    domain = sys.argv[2]

    if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
        log.fatal("SSL certificate is required. See README.md.")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=443,
        ssl_certfile=f"/etc/letsencrypt/live/{domain}/fullchain.pem",
        ssl_keyfile=f"/etc/letsencrypt/live/{domain}/privkey.pem",
        timeout_keep_alive=10
    )

else:
    log.fatal("Unsupported protocol - choose http or https")
    exit(1)
