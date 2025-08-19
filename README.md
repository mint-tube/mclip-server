# Metaclip Server

## Setup

- Install packages for the python environment you will use (system-wide, venv, conda)
  
- Put a token for every user in `data/tokens.txt` (any text, separated by new lines)

- Optional: Install `certbot` for https certificates

- Optional: Change prompts for domain and email to static values

- `python3 main.py` to start server at :443 or :80  
  
*Note: Python >= 3.12 required*


## Database Schema
```sql
CREATE TABLE items (
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` should be somewhat unique - collisions will be treated as a client error
- `type` can be either 'text' or 'file`
- `name` stores the filename or text identifier
- `content` must be binary; X'6a682f9b0e..' in query



## API Endpoints

### Health Check
- **HEAD** `/api`
- **Description:** Server health check
- **Response Body:** `healthy`


### SQL Query
- **POST** `/api`
- **Description:** Execute SQL query in the database
- **Request:**  
  ```yaml
  Authorization: <token>
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
  - Note: `content` is a hex-encoded UTF-8 string.
- **Errors:**
  - 400: Bad request / Invalid Content-Type
  - 401: Invalid auth token
  - 422: Forbidden command: \<command> / Invalid query
  - 500: Internal server error

### Suggested Operations

#### Read Operations
```sql
-- Get all items
SELECT * FROM items;

-- Get specific item by ID
SELECT * FROM items WHERE id = '550e8400e29b41d4a7164466';

-- Get items by ID prefix
SELECT * FROM items WHERE id LIKE '550e*';

-- Get items by type
SELECT * FROM items WHERE type = 'text';

-- Get items by name pattern
SELECT * FROM items WHERE name LIKE '%document%';
```

#### Write Operations
```sql
-- Insert new text item
INSERT INTO items (id, type, name, content) VALUES ('550e8400e29b41d4a7164466','text', 'hello', X'48656c6c6f20776f726c64');

-- Insert new file item
INSERT INTO items (id, type, name, content) VALUES ('9159ab07d29945b42ac62a68', 'file', 'document.pdf', X'255044462d312e340a...');

-- Updating items is forbidden because some clients use content caching
```

#### Delete Operations
```sql
-- Delete specific item
DELETE FROM items WHERE id = '550e8400e29b41d4a7164466';

-- Delete items by ID prefix
DELETE FROM items WHERE id LIKE '550e84*';

-- Delete all items
DELETE FROM items;
```

### Security Restrictions

These SQL operations are ALLOWED:
- `SELECT`, `INSERT`, `DELETE`

Most other SQL operations are BLOCKED, including but not limited to:
- `DROP`, `ALTER`, `CREATE`, `UPDATE`, `UPSERT`
---
### Leave a star! 🩵
