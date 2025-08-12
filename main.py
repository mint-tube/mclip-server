from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException,
    Response, Header, UploadFile, File
)
from pydantic import BaseModel
import sqlite3, json, uuid, os

app = FastAPI()

def get_db() -> sqlite3.Connection:
    """Get a connection to sqlite db with row factory"""
    conn = sqlite3.connect("data/sqlite.db")
    conn.row_factory = sqlite3.Row  # item(0) -> item["id"]
    return conn

def make_dirs() -> None:
    os.makedirs(os.path.dirname("data/sqlite.db"), exist_ok=True)
    os.makedirs("data/files/", exist_ok=True)
    
def init_get_db() -> None:
    conn = get_db()
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
    return os.path.join("data/files/", item_id)

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
                # Connection unreachable, mark for removal
                dead_connections.append(connection)
        
        # Remove dead connections
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
    
    conn = get_db()
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
    return Response(status_code=201, content=item_id)

@app.get("/items", response_model = list[Item])
async def get_items():
    """Get all items"""

    conn = get_db()
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
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        #404 Not found
        raise HTTPException(status_code=404, detail="Item doesn't exist")
    
    return Item(
        id=item["id"],
        type=item["type"],
        content=item["content"]
    )

@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete an item by ID"""
    conn = get_db()
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

# r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}$'
# uuid4 regex (just in case)

@app.head("/file/{item_id}")
async def head_file(item_id: str):
    """Get file metadata (HEAD request)"""
    conn = get_db()
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item["type"] != "file":
        raise HTTPException(status_code=415, detail="Not a file")
    
    file_path = os.path.join("data/files/", item_id)
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
                return HTTPException(status_code=416, detail="Invalid range")
            
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
            return HTTPException(status_code=400, detail="Invalid range format")
    
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item doesn't exist")
    
    if item["type"] != "file":
        raise HTTPException(status_code=400, detail="Not a file")
    
    file_path = os.path.join("data/files/", item_id)
    
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
    init_get_db()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
