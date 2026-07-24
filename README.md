# mclip server

## Setup

`pip install -r requirements.txt`  
(fastapi, uvicorn, slowapi)
  
To run over **http**:
- `sudo python3 main.py http`

To run over **https**:
- Get a Let's encrypt SSL certificate (`sudo certbot certonly --standalone --agree-tos`)
- `sudo python3 main.py <your_domain>`

You can always change the port numbers. By default, :80 is used for http and :443 for https.

## Database Schema

```sql
CREATE TABLE items (
    id TEXT PRIMARY KEY,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` is a UUID v4.
- `timestamp` is a UTC timestamp in `YYYY-MM-DD HH:MM:SS`
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
  Authorization: Basic base64(<username>:<password>)
  ```
  **URL-encoded query parameters (all optional):**
  - `type` - `"text"` or `"file"`
  - `name` - string with wildcards: `%` for 1 or more characters, `_` for exactly 1 character, `\` to escape.
  - `limit` - max number of items in response, defaults to `100`.
  - `offset` - number of items to skip, default to `0`.
  - `altered_after` - UTC timestamp in format `"YYYY-MM-DD HH:MM:SS"`.
  - `include_content` - Return full content if `true`, otherwise first 180 bytes for text and no content for files. Defaults to `false`
- **Response:**
  ```yaml
  Content-Type: application/json
  ```
  ```json
  [
    {
      "id": "9358eee7-5325-4394-bf7c-fc909507094f",
      "timestamp": "2026-06-27 01:12:06",
      "type": "text",
      "name": "hello.txt",
      "content": "SGVsbG8gV29ybGQh"
    }
  ]
  ```
- **Status Codes:**
  - 200 OK
  - 400 Bad Request: **Invalid query parameters** (details in the response body)
  - 401 Unauthorized: **Invalid credentials**


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
  - 400 Bad Request: **Malformed JSON / Missing fields**
  - 401 Unauthorized:  **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type**
  - 422 Unprocessable Content: **Invalid item type / Content is not base64**


<!-- Get item? -->


### Alter item
- **PATCH** `/api/items/{id}`
- **Request:**
  ```yaml
  Content-Type: application/json
  Authorization: Basic base64(<username>:<password>)
  ```
  ```json
  {
    // At least one
    "name": "Quick notes",
    "content": "bWludC10dWJlL21obA=="
  }
  ```
- **Status codes:**
  - 204 No Content
  - 400 Bad request: **Malformed JSON/ No changes specified**
  - 404 Not found: **No item with provided ID**
  - 415 Unsupported Media Type: **Invalid Content-Type**
  - 422 Unprocessable Content: **Content is not base64**
- **Note:** Timestamp will be updated


### Delete item
- **DELETE** `/api/items/{id}`
- **Request:**
  ```yaml
  Authorization: Basic base64(<username>:<password>)
  ```
- **Status codes:**
  - 204 No Content
  - 404 Not Found: **No item with provided ID**


### Check name availability
- **HEAD** `/api/account/{username}`
- **Status codes:**
  - 200 OK
  - 409 Conflict: **Name not available**


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