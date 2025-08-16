#! /bin/env python3

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.gzip import GZipMiddleware
from typing import Any
from base64 import b64encode
import sqlite3, json, os, subprocess, uvicorn
import logging
import sys

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored level names"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    # add color to levelname
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = self.COLORS[record.levelname] + record.levelname + self.RESET
        
        return super().format(record)

# Configure logger to match FastAPI's format with colors
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter("%(levelname)s:     %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
log = logging.getLogger()

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

def db_exec(query: str, token: str) -> list[dict[str, Any]]:
    """Execute a query in data/<token>.db"""
    conn = sqlite3.connect(f"data/{token}.db", autocommit=True)
    conn.row_factory = sqlite3.Row  # item[0] -> item["id"]
    fetched = conn.execute(query).fetchall()
    if fetched:
        fetched = [dict(row) for row in fetched]
    conn.close()
    return fetched

    
def init_db(token: str) -> None:
    """Initialize a database for user"""
    db_exec('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            content BLOB NOT NULL
        )''', token=token)

def path_to(item_id: str) -> str:
    return f"data/files/{item_id}"

def is_valid_token(token: str) -> bool:
    """Read data/tokens.txt, check if token is one of lines"""

    try:
        with open("data/tokens.txt", "r", encoding="utf-8") as file:
            for line in file:
                if line.strip() == token:
                    return True
    except FileNotFoundError:
        # tokens.txt doesn't exist
        log.fatal("PUT TOKENS IN data/tokens.txt !!!")
    
    return False

def is_valid_query(query: str) -> tuple[bool, str]:
    blacklist = [
        "CREATE", "ALTER", "DROP", "UPDATE", "REPLACE", "UPSERT",
        "ATTACH", "DETACH", "VACUUM", "PRAGMA", "CAST", "UNION"
    ]
    for banned in blacklist:
        if banned in query:
            return (False, banned)
    return (True, "")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api")
async def api(request: Request):
    """Execute a SQL query sent in text/plain, return result in json"""

    content_type = request.headers.get("Content-Type")
    auth_token = request.headers.get("Authorization")
    
    if (auth_token is None) or (not is_valid_token(auth_token)):
        raise HTTPException(status_code=401,
                            detail="Invalid auth token")

    if content_type not in ("text/plain", "text/plain; charset=utf-8"):
        raise HTTPException(status_code=400,
                            detail="Invalid Conent-Type")
    
    content = await request.body()
    content = content.decode("utf-8")
    
    validation_res = is_valid_query(content)
    if validation_res[0] is False:
        raise HTTPException(status_code=422,
                            detail=f"Forbidden command: {validation_res[1]}")

    try:
        init_db(auth_token)
        result = db_exec(content, auth_token)
        # Convert BLOB bytes to base64 strings
        for row in result: row['content'] = b64encode(row['content'])
        processed_result = [row['content'] for row in result]
        return Response(media_type="application/json",
                    content=json.dumps(processed_result))
    except sqlite3.Error as e:
        log.exception(e)
        raise HTTPException(status_code=422,
                            detail=f"Query execution failed")
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=500,
                            detail="Internal server error")



if __name__ == "__main__":
    app.add_middleware(GZipMiddleware)
    cert_info = {"certfile": None, "keyfile": None}

    cert_choice = input("Renew SSL sertificates? (y/n/http): ")
    if cert_choice == 'http':
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=80,
            timeout_keep_alive=10
        )
        exit(0)

    elif cert_choice == 'y':
        domain    = input("Your domain:\n")
        email     = input("Your emai:\n")

        # Get SSL certificates
        try:
            if domain and email:
                cert_info = get_cert(domain, email)
                log.info(f"SSL certificates loaded for {domain}")
            else:
                log.warning(f"Domain or email not specified, http-only")
        except Exception as e:
            log.error(f"Failed to load SSL certificates: \n{e}")
            exit(1)

    elif cert_choice == 'n':
        domain = input("Your domain:\n")
        
        # Use existing SSL certificates from certbot
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
        
        # Check if certificate files exist
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            log.error(f"SSL certificates not found for domain {domain}")
            log.error("Please ensure certificates exist or run with 'y' to generate new ones")
            exit(1)
        
        cert_info = {
            "certfile": cert_path,
            "keyfile": key_path
        }
        log.info(f"Using existing SSL certificates for {domain}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=443,
        ssl_certfile=cert_info["certfile"],
        ssl_keyfile=cert_info["keyfile"],
        timeout_keep_alive=10
    )
