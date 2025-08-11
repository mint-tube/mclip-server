# Metaclip Server

## Setup
- Copy `config.example` to `config`, fill with your options
  
- `python3 main.py` to start at http://localhost:8000

**Note:**  Middleware (e.g. caddy, nginx) required for https, compression and reverse proxy (myserver.com -> localhost:8000)


## API Endpoints

### Health Check
- **GET** `/`
- **Description**: Server health check
- **Response**: 
  ```json
  {
    "status": "healthy"
  }
  ```

### Items Management

#### Create Item
- **POST** `/items`
- **Description**: Create a new item (text or file metadata)
- **Request Body**:
  ```json
  {
    "type": "text",
    "content": "Hello world"
  }
  ```
  or
  ```json
  {
    "type": "file",
    "content": "document.pdf"
  }
  ```
- **Response**: 201 Created
- **Errors**:
  - 400: Items must have content
  - 422: Type must be 'text' or 'file'

#### Get All Items
- **GET** `/items`
- **Description**: Retrieve all items from the database
- **Response**: 
  ```json
  [
    {
      "id": "9159ab07-d299-45b4-2ac6-2a681b256880",
      "type": "text",
      "content": "Hello world"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "file",
      "content": "document.pdf"
    }
  ]
  ```

#### Get Specific Item
- **GET** `/items/{item_id}`
- **Description**: Retrieve an item by ID
- **Parameters**:
  - `item_id`: UUID of the item
- **Response**: 
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "text",
    "content": "Hello world"
  }
  ```
- **Errors**: 404: Item doesn't exist 

#### Delete Item
- **DELETE** `/items/{item_id}`
- **Description**: Delete an item by ID
- **Parameters**:
  - `item_id`: UUID of the item
- **Response**: 204 No Content
- **Errors**: 404: Item doesn't exist

### File Operations

#### Get File length
- **HEAD** `/file/{item_id}`
- **Description**: Get file length without downloading it
- **Parameters**:
  - `item_id`: UUID of the file item
- **Response Headers**:
  - `Content-Length`: File size in bytes
  - `Content-Type`: application/octet-stream
- **Error Responses**:
  - 404: Item not found
  - 410: File lost
  - 415: Not a file

#### Download File
- **GET** `/file/{item_id}`
- **Description**: Download file content with optional range support
- **Parameters**:
  - `item_id`: UUID of the file item
- **Headers**:
  - `range` (optional): Range of bytes for partial download (e.g., "bytes=0-499")
- **Response**: Binary file representation
- **Response Headers**:
  - `Content-Length`: File size in bytes
  - `Content-Type`: application/octet-stream
  - `Content-Range`: same as `range` (if provided)
- **Status Codes**:
  - 200: Full content
  - 206: Partial content
- **Errors**:
  - 400: Invalid range format
  - 404: Item doesn't exist
  - 410: File lost
  - 415: Not a file
  - 416: Invalid range
  
#### Upload File
- **PUT** `/file/{item_id}`
- **Description**: Upload content of an existing file item
- **Parameters**:
  - `item_id` (path): UUID of the file item
- **Request Body**: File content as binary data (multipart/form-data)
- **Response**: HTTP 201 Created (no content body)
- **Error Responses**:
  - HTTP 404: Item doesn't exist
  - HTTP 400: Not a file
  - HTTP 500: Failed to write file

### WebSocket

- **WebSocket** `/ws`
- **Description**: Real-time notifications for item creation and deletion
- **Messages**:
  - **Server → Client**: Item creation notification
    ```json
    {
      "type": "created",
      "item_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
  - **Server → Client**: Item deletion notification
    ```json
    {
      "type": "deleted",
      "item_id": "9159ab07-d299-45b4-2ac6-2a681b256880"
    }
    ```
  - **Client → Server**: Heartbeat check
    ```json
    {
      "type": "ping"
    }
    ```
  - **Server → Client**: Heartbeat proof
    ```json
    {
      "type": "pong"
    }
    ```

---
### Leave a star! 🩵