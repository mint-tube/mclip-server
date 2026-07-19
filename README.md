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
    access TEXT NOT NULL
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` should be unique - collisions will be treated as a client error
- `access` can be either 'public' or 'private'
- `type` can be either 'text' or 'file`
- `name` stores the name of the file or text note
- `content` is binary; use X'...' to insert hex-encoded data


## API Endpoints

A JSON message is sent with status codes 4XX and 5XX.

### Health Check
- **HEAD** `/api`
- **Description:** Server status check
- **Status Codes:**
  - 204 OK

### SQL Query
- **POST** `/api/query`
- **Description:** Execute SQL query in the database
- **Request:**  
  ```yaml
  Authorization: Basic base64(<user>:<password>)
  Content-Type: text/plain; charset=utf-8
  ```
  ```sql
  SELECT * FROM items
  ```
- **Response:** 
  ```yaml
  Content-Type: application/json
  ```
  ```json
  [
    {
      "id": "550e8400e29b41d4a7164466",
      "type": "text",
      "name": "Hello World",
      "content": "48656c6c6f20576f726c64"
    },
    {
      "id": "9159ab07d29945b42ac62a68",
      "type": "file",
      "name": "document.pdf",
      "content": "f27d0953c1be8197..."
    }
  ]
  ```
  Note: `content` is a base64-encoded UTF-8 string.
- **Status codes:**
  - 200 OK
  - 400 Bad Request: **Malformed query**
  - 401 Unauthorized: **Invalid credentials**
  - 415 Unsupported Media Type: **Invalid Content-Type header**
  - 422 Unprocessable Content: **Query contains forbidden elements**
  - 500 Internal Server Error: **Try again**

### Create account
- **POST** `/api/account`
- **Description:** Create an account with given name and password
- **Request:**
  ```yaml
  Authorization: Basic base64(<user>:<password>)
  ```
  Note: User's name and password must consist of 3 to 100 letters, digits, underscores, periods and dashes.
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
  Authorization: Basic base64(<user>:<old_password>)
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

## Suggested Operations

#### Read Operations
```sql
-- Get all items, only fetch first 150 bytes of content
SELECT id, type, name, substr(content, 1, 150) FROM items;

-- Get specific item by ID
SELECT * FROM items WHERE id = '550e8400e29b41d4a7164466';

-- Get items by ID prefix
SELECT id, type, name, substr(content, 1, 150) FROM items WHERE id LIKE '550e%';

-- Get items by type
SELECT * FROM items WHERE type = 'text';

-- Get items by name pattern
SELECT id, type, name, substr(content, 1, 150) FROM items WHERE name LIKE '%document%';
```

Note that large files may be stored in the database, so you should not fully fetch all the contents on every update.

#### Write Operations
```sql
-- Insert new text item
INSERT INTO items (id, type, name, content) VALUES ('550e8400e29b41d4a7164466','text', 'hello', X'48656c6c6f20776f726c64');

-- Insert new file item
INSERT INTO items (id, type, name, content) VALUES ('9159ab07d29945b42ac62a68', 'file', 'document.pdf', X'255044462d312e340a...');

-- Updating items is discouraged due to content caching
```

#### Delete Operations
```sql
-- Delete specific item
DELETE FROM items WHERE id = '550e8400e29b41d4a7164466';

-- Delete items by ID prefix
DELETE FROM items WHERE id LIKE '550e84%';

-- Delete all items
DELETE FROM items;
```

### Forbidden Operations
These SQL operations are explicitly FORBIDDEN:
- `DROP`, `ALTER`, `CREATE`, `EXPLAIN`, `UPSERT`, `ATTACH`, `DETACH`, `PRAGMA`, `readfile()`

<!-- ### Mclip clients -->

---
# Leave a star! 🩵