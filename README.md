# mclip server

## Setup

`pip install -r requirements.txt`  
(fastapi, uvicorn, slowapi, bcrypt)
  
To run over **http**:
- `./main.py http`

To run over **https**:
- Get a Let's encrypt SSL certificate (`sudo certbot certonly --standalone --agree-tos`)
- `./main.py https <your_domain>`

## Database Schema
```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    access TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` is a UUID v4.
- `timestamp` is a UTC timestamp in `YYYY-MM-DD HH:MM:SS`
- `access` is 'public' or 'private'
- `type` can be either 'text' or 'file`.
- `name` stores the name of the entry.
- `content` is binary; encoded as base64 in responses.


## API Endpoints

### Status check
- **HEAD** `/api`
- **Status Codes:**
  - 204 OK

### List items
- **GET** `/api/items`
- **Request:**
  ```yaml
  Content-Type: application/json
  Authorization: Basic base64(<username>:<password>)
  ```
  ```json
  // All filters are optional.
  {
    "access": "private", // "public" or "private"
    "type": "file", // "text" or "file"
    "name": "%.txt", // `%` for 1 or more, `_` for exactly 1, `\` to escape
    "id_prefix": "550e",
    "limit": 100, // Defaults to 100. 
    "offset": 0, // Defaults to 0.
    "altered_after": "2026-06-26 09:10:08", // UTC timestamp
    "include_content": false // Full content if `true`, otherwise first 150 symbols for text and no content for files. Defaults to `false`
  }
  ```
- **Response:**
  ```yaml
  Content-Type: application/json
  ```
  ```json
  [
    {
      "id": "9358eee7-5325-4394-bf7c-fc909507094f",
      "access": "private",
      "timestamp": "2026-06-27 01:12:06"
      "type": "text",
      "name": "hello.txt",
      "content": "SGVsbG8gV29ybGQh"
    }
  ]
  ```
- **Status Codes:**
  - 200 OK
  - 400 Bad Request: **Invalid query parameters**
  - 401 Unauthorized: **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type**

### Create item
- **POST** `/api/items`
- **Request:**
  ```yaml
  Content-Type: application/json
  Authorization: Basic base64(<username>:<password>)
  ```
  ```json
  {
    // ID and timestamp are auto‑generated
    "access": "public", // "public" or "private"
    "type": "text", // "text" or "file"
    "name": "TODO list",
    "content": "U2xlZXAgMTIgaG91cnM=" // base64 encoded
  }
  ```
- **Response:**
  ```yaml
  Content-Type: text/plain; charset="utf-8"
  ```
  ```
  425c8490-0f5c-474b-b2ab-20eba07fddda // Generated ID
  ```
- **Status codes:**
  - 201 Created
  - 400 Bad Request: **Malformed JSON/base64**
  - 401 Unauthorized:  **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type**
  - 422 Unprocessable Content: **Invalid item type**

### Alter item
- **PATCH** `/api/items`
- **Request:**
  ```yaml
  Content-Type: application/json
  Authorization: Basic base64(<username>:<password>)
  ```
  ```json
  {
    "id": "425c8490-0f5c-474b-b2ab-20eba07fddda",
    // One or more of the following - "access", "name", "content"
    "access": "public",
    "name": "Quick notes",
    "content": "bWludC10dWJlL21obA=="
  }
  ```
- **Status codes:**
  - 204 No Content
  - 400 Bad request: **Malformed JSON/base64**
  - 404 Not found: **No items with provided ID**
  - 415 Unsupported Media Type: **Invalid Content-Type**
- **Note:** Timestamp will be updated

### Delete item
- **DELETE** `/api/items`
- **Request:**
  ```yaml
  Content-Type: text/plain; charset="utf-8"
  Authorization: Basic base64(<username>:<password>)
  ```
  ```
  425c8490-0f5c-474b-b2ab-20eba07fddda
  ```
- **Status codes:**
  - 204 No Content
  - 404 Not Found: **No items with provided ID**
  - 415 Unsupported Media Type: **Invalid Content-Type**

### List user's public files
- **GET** `/api/items/{username}`
- **Request:**
  ```yaml
  Content-Type: text/json"
  ```
  ```json
  // All filters are optional.
  {
    "type": "text", // "text" or "file"
    "name": "ed25519\___", // `%` for 1 or more, `_` for exactly 1, `\` to escape
    "id_prefix": "0dc43",
    "limit": 5, // Defaults to 100
    "offset": 10, // Defaults to 0
    "altered_after": "2026-05-14 15:02:28", // UTC timestamp
    "include_content": false // Full content if `true`, otherwise first 150 symbols for text and no content for files. Defaults to `false`
  }
  ```
- **Response:**
  ```yaml
  Content-Type: application/json
  ```
  ```json
  [
    // 11-th public item matching the filters
    {
      "id": "0dc4395a-639d-4220-a056-3a8895a8fd41",
      "timestamp": "2026-05-15 20:23:03",
      "access": "public",
      "type": "text",
      "name": "ed25519_02",
      "content": "QUFBQUMzTnphQz..."
    }
  ]
  ```
- **Status codes:**
  - 200 OK
  - 400 Bad Request: **Invalid query parameters**
  - 404 Not Found: **No user with such name**
  - 415 Unsupported Media Type: **Invalid Content-Type**

### Check user's existance
- **HEAD** `/api/items/{username}`
- **Status codes:**
  - 204 No Content
  - 404 Not Found: **User doesn't exist**

### Create account
- **POST** `/api/account`
- **Request:**
  ```yaml
  Authorization: Basic base64(<username>:<password>)
  ```
- **Status codes:**
  - 201 Created
  - 400 Bad Request: **Invalid Authorization header**
  - 409 Conflict: **Name not available**
  - 422 Unprocessable Content: **Unacceptable name or password**
- **Note:** User's name and password must consist of 3 to 100 letters, digits, underscores, periods and dashes.

### Change password
- **PATCH** `/api/account`
- **Request:**
  ```yaml
  Content-Type: text/plain; charset=utf-8
  Authorization: Basic base64(<username>:<old_password>)
  ```
  ```yaml
  <new_password>
  ```
- **Status codes:**
  - 204 No Content
  - 401 Unauthorized: **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type**
  - 422 Unprocessable Content: **New password is unacceptable**

### Delete account
- **DELETE** `/api/account`
- **Request:**
  ```yaml
  Authorization: Basic base64(<username>:<password>)
  ```
- **Status codes:**
  - 204 No Content
  - 401 Invalid Credentials

---

# Leave a star! 🩵