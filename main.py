from configparser import ConfigParser
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException,\
                    Response, Header, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
import json
import uuid
from datetime import datetime
import os
from re import match

# Configuration
config = ConfigParser()
config.read('config')
fastapi_port = int(config.get('FastAPI', 'port'))
log_level = config.get('FastAPI', 'log_level')
db_file = config.get('SQLite', 'db_file')
files_dir = config.get('SQLite', 'files_dir')

app = FastAPI()

def db():
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def make_dirs():
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)
    
def init_db():
    conn = db()
    conn.cursor().execute('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN ('text', 'file')),
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

def path_to(item_id: str) -> str:
    return os.path.join(files_dir, item_id)

# Pydantic models for request/response
class Item(BaseModel):
    id: str | None = None
    type: str
    content: str | None = None

# WebSocket connection manager for broadcasting changes
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Connection might be dead, mark for removal
                dead_connections.append(connection)
        
        # Remove dead connections after iteration
        for dead_connection in dead_connections:
            self.active_connections.remove(dead_connection)

manager = ConnectionManager()

@app.post("/items")
async def create_item(item: Item):
    "Create a new item"

    if item.type not in ['text', 'file']:
        #422 Unprocessable Entity
        raise HTTPException(status_code=422, detail="Type must be 'text' or 'file'")
    
    item_id = str(uuid.uuid4())

    if not item.content:
        #400 Bad Request
        raise HTTPException(status_code=400, detail="Items must have content")

    if item.type == 'file':
        # Create empty file
        with open(path_to(item_id), 'wb') as f: pass
    
    conn = db()
    cursor = conn.cursor()
    
    # Store content directly (for text items: text content, for file items: file name)
    cursor.execute('''
        INSERT INTO items (id, type, content)
        VALUES (?, ?, ?)
    ''', (item_id, item.type, item.content))
    
    conn.commit()
    conn.close()
    
    # Broadcast to all connected clients that a new item was created
    await manager.broadcast(json.dumps({
        "type": "created",
        "item_id": item_id
    }))
    
    #201 Created
    return Response(status_code=201, content=item_id, media_type="text/plain")

@app.get("/items", response_model = list[Item])
async def get_items():
    """Get all items"""

    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM items ORDER BY rowid DESC"
    )
    items = cursor.fetchall()
    conn.close()
    
    result = []
    for item in items:
        result.append(Item(
            id=item["id"],
            type=item["type"],
            content=item["content"]
        ))
    
    return result

@app.get("/items/{item_id}", response_model = Item)
async def get_item(item_id: str):
    """Get an item by ID"""
    
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        #404 Not found
        raise HTTPException(status_code=404, detail="Item not found")
    
    return Item(
        id=item["id"],
        type=item["type"],
        content=item["content"]
    )

@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete an item by ID"""
    conn = db()
    cursor = conn.cursor()
    # Check if item exists
    cursor.execute("SELECT id, type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item doesn't exist")
    
    # If it's a file, delete the actual file
    if item["type"] == "file":
        if os.path.exists(path_to(item_id)):
            os.remove(path_to(item_id))
    
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    await manager.broadcast(json.dumps({
        "type": "deleted",
        "item_id": item_id
    }))
    
    return Response(status_code = 204) # No Content

# WebSocket endpoint for real-time notifications
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive and handle client messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    # Heartbeat/keepalive
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# def verify_id(item_id: str) -> None:
#     if not match(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$', item_id):
#         pass                          # ^ uuid4 regex ^

@app.head("/file/{item_id}")
async def head_file(item_id: str):
    """Get file metadata (HEAD request)"""
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["type"] != "file":
        raise HTTPException(status_code=415, detail="Not a file")
    
    if not os.path.exists(path_to(item_id)):
        raise HTTPException(status_code=410, detail="File lost")
    
    file_size = os.path.getsize(path_to(item_id))
    
    return Response(
        status_code=200,
        headers={
            "Content-Length": str(file_size),
            "Content-Type": "application/octet-stream"
    })

@app.get("/file/{item_id}")
async def get_file(item_id: str, range: str | None = Header(None)):
    """Get file content with optional range support"""
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["type"] != "file":
        raise HTTPException(status_code=415, detail="Not a file")
    
    file_path = os.path.join(files_dir, item_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=410, detail="File lost")
    
    file_size = os.path.getsize(file_path)
    
    if range:
        # Parse range header: "bytes=start-end"
        range_str = range[6:]  # Remove "bytes="
        try:
            start_str, end_str = range_str.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            
            # Validate range
            if start < 0 or end >= file_size or start > end:
                return Response(status_code=416)
            
            # Read the specified range
            with open(file_path, 'rb') as f:
                f.seek(start)
                content = f.read(end - start + 1)
            
            return Response(
                content=content,
                status_code=206, # Partial Content
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(content)),
                    "Content-Type": "application/octet-stream"
                }
            )
        except (ValueError, IndexError):
            return Response(status_code=400, content="Invalid range")
    
    # Return full file
    with open(file_path, 'rb') as f:
        content = f.read()
    
    return Response(
        content=content,
        status_code=200, # OK
        headers={
            "Content-Length": str(file_size),
            "Content-Type": "application/octet-stream"
        }
    )

@app.put("/file/{item_id}")
async def upload_file(item_id: str, file: UploadFile = File(...)):
    """Upload file content for an existing file item"""
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item doesn't exist")
    
    if item["type"] != "file":
        raise HTTPException(status_code=400, detail="Not a file")
    
    file_path = os.path.join(files_dir, item_id)
    
    try:
        # Save the uploaded file content
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")
    
    return Response(status_code=201)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    make_dirs()
    init_db()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=fastapi_port, log_level=log_level)
