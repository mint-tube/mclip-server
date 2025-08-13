from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException,
    Response, Header, UploadFile, File
)
from fastapi.middleware.gzip import GZipMiddleware
from typing import Any
import sqlite3, json, os, subprocess, ssl, uvicorn

app = FastAPI()


def get_cert(domain, email):
    """Issue Let's Encrypt certificate using certbot"""
    cmd = [
        "certbot", "certonly",
        "--standalone",
        "--email", email,
        "--agree-tos",
        "--non-interactive",
        "-d", domain
    ]
    subprocess.run(cmd, check=True)
    
    return {
        "certfile": f"/etc/letsencrypt/live/{domain}/fullchain.pem",
        "keyfile": f"/etc/letsencrypt/live/{domain}/privkey.pem"
    }

def db_exec(query: str, token: str) -> list[dict[str, Any]] | None:
    """Execute a query in data/<token>.db"""
    conn = sqlite3.connect(f"data/{token}.db", autocommit=True)
    conn.row_factory = sqlite3.Row  # item[0] -> item["id"]
    fetched = conn.execute(query).fetchall()
    conn.close()
    return fetched

    
def init_db(token: str) -> None:
    """Initialize a database for user"""
    db_exec('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
        )''', token=token)

def path_to(item_id: str) -> str:
    return f"data/files/{item_id}"


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    os.makedirs("data/files", exist_ok=True)
    
    # Initialize SSL variables
    cert_info = {"certfile": None, "keyfile": None}
    use_ssl   = False
    domain    = input("Enter your domain (required for https):\n")
    email     = input("Your email (required for https):\n")

    # Get SSL certificates
    try:
        if domain and email:
            cert_info = get_cert(domain, email)
            use_ssl = True
            print(f"SSL certificates loaded for {domain}")
        else:
            print(f"Domain or email not specified, http-only")
    except Exception as e:
        print(f"Failed to load SSL certificates: {e}")

    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=443 if use_ssl else 80,
        ssl_certfile=cert_info["certfile"] if use_ssl else None,
        ssl_keyfile=cert_info["keyfile"] if use_ssl else None,
        timeout_keep_alive=10
    )
