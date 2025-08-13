# Metaclip Server

## Setup
- Change prompts for domain and email to static values if needed

- Install packages for the python environment you will use (system-wide or in a venv)
  
- Install `certbot` for https certificates

- Add a token (9 bytes must suffice) for each user to `/data/tokens.txt`

- `python3 main.py` to start server at :443 or :80



## Database Schema
```sql
CREATE TABLE items (
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    content BLOB NOT NULL
);
```

- `id` should be somewhat unique, uuid suggested - collisions will be treated as a database error
- `type` can be either 'text' or 'file`
- `name` stores the filename or text identifier
- `content` stores the actual data as BLOB; must be like X'6C6F20..' or base64'yGVsb8g...' or just 'Hello World' in query



## API Endpoints

### Health Check
- **HEAD** `/api`
- **Description**: Server health check
- **Response Body**: healthy


### SQL Query
- **POST** `/api`
- **Description**: Execute SQL queries against the database
- **Headers**:
  - `Authorization`: `<token>`
- **Request Body**: SELECT * FROM items WHERE id LIKE '550e*'
- **Response Body**: 
  ```json
  [
    ["550e8400e29b41d4a716446655440000", "text", "", "SGVsbG8gd29ybGQ="],
    ["550e8400e29b41d4a716446655440001", "file", "document.pdf", "JVBERi0xLjQK..."]
  ]
  ```
  - Note: `content` is returned as base64-encoded text
- **Errors**:
  - 400: Bad request / Invalid Content-Type
  - 401: Invalid auth token
  - 422: Forbidden command: \<command> / Query execution failed
  - 500: Internal server error

### Suggested Operations

#### Read Operations
```sql
-- Get all items
SELECT * FROM items;

-- Get specific item by ID
SELECT * FROM items WHERE id = '550e8400e29b41d4a716446655440000';

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
INSERT INTO items (id, type, name, content) VALUES ('550e8400e29b41d4a716446655440000', 'text', 'hello', X'48656c6c6f20776f726c64');

-- Insert new file item
INSERT INTO items (id, type, name, content) VALUES ('9159ab07d29945b42ac62a681b256880', 'file', 'document.pdf', X'255044462d312e340a...');

-- Updating items is forbidden because some clients use content caching
```

#### Delete Operations
```sql
-- Delete specific item
DELETE FROM items WHERE id = '550e8400e29b41d4a716446655440000';

-- Delete items by ID prefix
DELETE FROM items WHERE id LIKE '550e84*';

-- Delete all items
DELETE FROM items;
```

### Request/Response Format

#### Request Format
plain/text
SQL_QUERY_IN_PLAIN_TEXT

#### Success Response Format
application/json
```json
[
  ["uuid1", "text", "name1", "base64_encoded_content1"],
  ["uuid2", "file", "name2", "base64_encoded_content2"]
]
```

### Security Restrictions

These SQL operations are ALLOWED:
- `SELECT`, `INSERT`, `DELETE`

Most other SQL operations are BLOCKED, including but not limited to:
- `DROP`, `ALTER`, `CREATE`, `UPDATE`, `UPSERT`

### Content Encoding

- **BLOB to Base64**: When returning BLOB data in JSON responses, content is base64-encoded
- **Base64 to BLOB**: When inserting BLOB data, clients should provide hex literals (`X'...'`) in SQL queries
- **Text Content**: For text items, content can be stored as plain text strings

---
### Leave a star! 🩵
