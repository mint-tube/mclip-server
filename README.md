# mclip server

## Setup

`pip install -r requirements.txt`  
(fastapi, uvicorn, slowapi)
  
To run over **http**:
- `./main.py http`

To run over **https**:
- Get a Let's encrypt SSL certificate (`sudo certbot certonly --standalone --agree-tos`)
- `./main.py https <your_domain>`

## Database Schema
```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` should be unique - collisions will be treated as a client error
- `type` can be either 'text' or 'file`
- `name` stores the name of the file or text note
- `content` is binary; use X'...' to insert hex-encoded data


## API Endpoints

If response has a body attached, it's JSON.  
All endpoints are protected with **HTTP Basic Authentication** (except for the Status Check)

### Status Check
- **HEAD** `/api`
- **Description:** Server status check
- **Status Codes:**
  - 204 OK

### List items
- **GET** `/api/items`
- **Description:** List items matching parameters
- **Request:**
  ```yaml
  Content-Type: application/json
  ```
  ```json
  // All filters are optional.
  {
    "type": "file", // "text" or "file"
    "name": "%.txt", // `%` for 1 or more char, `_` for exactly 1 char
    "id_prefix": "550e",
    "limit": 100, // Max number of entries. Defaults to 100. 
    "offset": 0, // Number of entries to skip. Defaults to 0.
    "include_content": false // If `true`, includes the full content; otherwise only first 200 bytes (base64-encoded)
  }
  ```
- **Response:**
  ```json
  [
    {
      "id": "550e8400e29b41d4a7164466",
      "type": "text",
      "name": "hello.txt",
      "content": "48656c6c6f20576f726c64"
    }
  ]
  ```
- **Status Codes:**
  - 200 OK
  - 400 Bad Request: **Invalid query parameters**
  - 401 Unauthorized: **Invalid credentials**

### Get Single Item
-- **GET** `/api/

### Create account
- **POST** `/api/account`
- **Description:** Create an account with name and password from the Authorization header. User's name and password must consist of 3 to 100 letters, digits, underscores, periods and dashes.
- **Status codes:**
  - 201 Created
  - 400 Bad Request: **Invalid Authtorization header**
  - 409 Conflict: **Name not available**
  - 422 Unprocessable Content: **Unacceptable name or password**

### Change password
- **PATCH** `/api/account`
- **Description:** Change password to account
- **Request:**
  ```yaml
  Content-Type: text/plain; charset=utf-8
  ```
  ```yaml
  <new_password>
  ```
- **Status codes:**
  - 204 No Content
  - 401 Unauthorized: **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type header**
  - 422 Unprocessable Content: **New password is unacceptable**

### Delete account
- **DELETE** `/api/account`
- **Description:** Delete account 
- **Status codes:**
  - 204 No Content
  - 401 Invalid Credentials

---

# Leave a star! 🩵