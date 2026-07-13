#! /bin/env python3
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.gzip import GZipMiddleware
from base64 import b64encode, b64decode
import sqlite3, json, os, uvicorn, subprocess, logging, sys

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    
    def format(self, record):
        record.levelname = self.COLORS[record.levelname] + record.levelname + '\033[0m'
        return super().format(record)

# Configure logger to match FastAPI's format with colors
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter("%(levelname)s:     %(message)s"))
logging.basicConfig( level=logging.INFO, handlers=[handler] )
log = logging.getLogger()

def db_exec(query: str, user: str) -> list[dict]:
    """Execute a query in data/<token>.db"""
    conn = sqlite3.connect(f"data/{user}.db", autocommit=True)
    conn.row_factory = sqlite3.Row 
    with conn:
        fetched = conn.execute(query).fetchall()
        return [dict(row) for row in fetched]

    
def init_db(user: str) -> None:
    """Initialize a database for user"""
    db_exec('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            content BLOB NOT NULL
        )''', user)

def validate_credentials(credentials: str) -> bool:
    """Read data/tokens.txt, check if token is one of lines"""
    with open("data/tokens.txt", "xr", encoding="utf-8") as file:
        for line in file:
            if line == credentials: return True
    
    return False

def validate_query(query: str) -> bool:
    query = query.upper() # <- 'create' == 'CREATE'
    blacklist = [
        "DROP", "ALTER", "CREATE", "EXPLAIN", "UPSERT", 
        "ATTACH", "DETACH", "PRAGMA", "READFILE"
    ]
    for banned in blacklist:
        if banned in query: return False
    return True


app = FastAPI()

@app.head("/api")
async def root():
    """Health check endpoint"""
    return "healthy"

@app.post("/api")
async def api(request: Request):
    """Execute a SQL query sent in text/plain, return result in application/json"""
    content_type = request.headers.get("Content-Type")
    credentials = request.headers.get("Authorization")
    content = (await request.body()).decode("utf-8")
    
    if content_type not in ("text/plain", "text/plain; charset=utf-8"):
        raise HTTPException(status_code=400, detail="Malformed request")
    
    if credentials is None or not validate_credentials(credentials):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not validate_query(content):
        raise HTTPException(status_code=422, detail="Query contains forbidden elements")

    try:
        result = db_exec(content, credentials.split(":")[0])
        # Convert binary to base64
        for row in result:
            if 'content' in row.keys(): row['content'] = b64encode(row['content'])
        return Response(media_type="application/json", content=json.dumps(result))
    except sqlite3.Error as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail="Malformed query")
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=500, detail="Internal server error")

app.add_middleware(GZipMiddleware)

if (len(sys.argv) == 1):
    log.fatal("Protocol not specified (http/https).")
    exit(1)

if sys.argv[1] == "http":
    if (len(sys.argv) > 2): log.info("Extra arguments are ignored")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
        timeout_keep_alive=10
    )

elif sys.argv[1] == "https":
    if (len(sys.argv) == 2):
        log.fatal("Domain not specified.")
        exit(1)
    if (len(sys.argv) > 3): log.info("Extra arguments are ignored")
    
    domain = sys.argv[2]

    if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
        rv = subprocess.run(["certbot", "certonly", "--standalone", "--agree-tos",
                             "--non-interactive", "-d", domain, "--silent"])
        if rv.returncode: exit(1)
        log.info(f"Received SSL certificates for {domain}")
    
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
