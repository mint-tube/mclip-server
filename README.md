# Metaclip Server

## Setup
**. . .**

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

### Create Item
- **POST** `/items`
- **Description**: Create a new item (text message or file metadata)
- **Request Body**:
  ```json
  {
    "type": "text",
    "content": "Hello world",
    "file_name": null
  }
  ```
  or

  ```json
  {
    "type": "file",
    "content": base64,
    "file_name": "document.pdf"
  }
  ```

#### Get All Items
- **GET** `/items`
- **Description**: Retrieve all items from the database
- **Response**: 
  ```json
  [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "type": "text",
      "content": "Hello world",
      "file_name": null
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "file",
      "content": null,
      "file_name": "document.pdf"
    }
    // Note - file's content has to be downloaded from /items/{item_id}
  ]
  ```

#### Get Specific Item
- **GET** `/items/{item_id}`
- **Description**: Retrieve a specific item by ID
- **Parameters**:
  - `item_id` (path): UUID of the item
- **Response**: 
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "text",
    "content": "Hello world",
    "file_name": null
  }
  ```
  or

  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "type": "file",
    "content": base64,
    "file_name": "document.pdf"
  }
  ```
- **Error Response**: HTTP 404 Not Found if item doesn't exist

#### Delete Item
- **DELETE** `/items/{item_id}`
- **Description**: Delete an item by ID
- **Parameters**:
  - `item_id` (path): UUID of the item
- **Response**: HTTP 204 No Content (no content body)
- **Error Response**: HTTP 404 Not Found if item doesn't exist

### WebSocket

#### WebSocket Endpoint
- **WebSocket** `/ws`
- **Description**: Real-time notifications for item creation and deletion
- **Messages**:
  - **Server → Client**: Item creation notification
    ```json
    {
      "type": "item_created",
      "item_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
  - **Server → Client**: Item deletion notification
    ```json
    {
      "type": "item_deleted",
      "item_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
  - **Client → Server**: Ping/Heartbeat
    ```json
    {
      "type": "ping"
    }
    ```
  - **Server → Client**: Pong response
    ```json
    {
      "type": "pong"
    }
    ```

### Error Responses

#### Validation Errors
- **HTTP 400 Bad Request**: Invalid request data
  ```json
  {
    "detail": "Text items cannot have file_name"
  }
  ```

#### Not Found Errors
- **HTTP 404 Not Found**: Item not found
  ```json
  {
    "detail": "Item not found"
  }
  ```

#### Validation Errors
- **HTTP 422 Unprocessable Entity**: Invalid item type
  ```json
  {
    "detail": "Type must be 'text' or 'file'"
  }
