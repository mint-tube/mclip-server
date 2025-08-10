from configparser import ConfigParser
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import sqlite3
import json
import uuid
from datetime import datetime
import os

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
            content TEXT,
            file_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Pydantic models for request/response
class Item(BaseModel):
    id: Optional[str] = None
    type: str
    content: Optional[str]
    file_name: Optional[str] = None

# WebSocket connection manager for broadcasting changes
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

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

# API Endpoints for CRUD operations

@app.post("/items")
async def create_item(item: Item):
    "Create a new item (text message or file metadata)"

    if item.type not in ['text', 'file']:
        raise HTTPException(status_code=422, detail="Type must be 'text' or 'file'")
    

    if item.type == 'text' and item.file_name:
        raise HTTPException(status_code=400, detail="Text items cannot have file_name")
    
    conn = db()
    cursor = conn.cursor()
    
    item_id = str(uuid.uuid4())
    
    cursor.execute('''
        INSERT INTO items (id, type, content, file_name)
        VALUES (?, ?, ?, ?)
    ''', (item_id, item.type, item.content, item.file_name))
    
    conn.commit()
    conn.close()
    
    # Broadcast to all connected clients that a new item was created
    await manager.broadcast(json.dumps({
        "type": "item_created",
        "item_id": item_id
    }))
    
    # Return 201 Created status (no content)
    return Response(status_code=201)

@app.get("/items", response_model=List[Item])
async def get_items():
    """Get all items with pagination"""

    conn = db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM items ORDER BY rowid DESC"
    )
    items = cursor.fetchall()
    conn.close()
    
    return [Item(
        id=item["id"],
        type=item["type"],
        content=item["content"],
        file_name=item["file_name"]
    ) for item in items]

@app.get("/items/{item_id}", response_model = Item)
async def get_item(item_id: str):
    """Get a specific item by ID"""
    conn = db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return Item(
        id=item["id"],
        type=item["type"],
        content=item["content"],
        file_name=item["file_name"]
    )

@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete an item"""
    conn = db()
    cursor = conn.cursor()
    
    # Check if item exists first
    cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
    
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    # Broadcast to all connected clients that an item was deleted
    await manager.broadcast(json.dumps({
        "type": "item_deleted",
        "item_id": item_id
    }))
    
    # Return 204 No Content status (no content)  
    return Response(status_code=204)

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

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Metaclip Server is running", "status": "healthy"}

if __name__ == "__main__":
    make_dirs()
    init_db()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=fastapi_port, log_level=log_level)
