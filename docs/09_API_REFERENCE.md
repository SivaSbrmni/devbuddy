# 09 — API Reference

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [08_DEPLOYMENT.md](./08_DEPLOYMENT.md)

---

## Base URLs

| Environment | URL |
|-------------|-----|
| Production | `https://devbuddy-backend.fly.dev` |
| Local | `http://localhost:8000` |

## Authentication

All protected endpoints require:
```
Authorization: Bearer <supabase_jwt_token>
```

Get token from Supabase Auth (frontend localStorage after login).

---

## Endpoints

### Health

#### GET /health
Public health check.

**Response**:
```json
{
  "status": "ok",
  "app": "DevBuddy Enterprise Agent Platform"
}
```

---

### Auth

#### GET /api/v1/auth/me
Get current user info.

**Auth**: Required

**Response**:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "tenant_id": "default"
}
```

---

### Chat

#### POST /api/v1/chat
Main chat endpoint. Returns Server-Sent Events (SSE) stream.

**Auth**: Required
**Rate Limit**: 30/hour per user

**Request**:
```json
{
  "message": "Build a React login form",
  "context": {
    "files": ["src/App.tsx"],
    "github_connection_id": "uuid"
  }
}
```

**Response** (SSE stream):
```
event: message
data: {"type": "token", "content": "I'll"}

event: message
data: {"type": "token", "content": " help"}

event: message
data: {"type": "task_created", "task_id": "uuid"}

event: done
data: {}
```

---

### Tasks

#### GET /api/v1/tasks
List user's tasks.

**Auth**: Required

**Query Params**:
- `status` (optional): Filter by status
- `limit` (optional): Default 20
- `offset` (optional): Default 0

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "description": "Build a form",
      "status": "COMPLETED",
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:35:00Z"
    }
  ],
  "total": 42
}
```

#### POST /api/v1/tasks
Create new task.

**Auth**: Required
**Rate Limit**: 6/hour per user

**Request**:
```json
{
  "description": "Create a Node.js API",
  "context": {
    "github_connection_id": "uuid"
  }
}
```

**Response**:
```json
{
  "id": "uuid",
  "status": "PENDING",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET /api/v1/tasks/{task_id}
Get task details.

**Auth**: Required

**Response**:
```json
{
  "id": "uuid",
  "description": "Create API",
  "status": "EXECUTING",
  "plan_json": {
    "subtasks": [
      {"id": 1, "description": "Setup express", "status": "COMPLETED"},
      {"id": 2, "description": "Add routes", "status": "IN_PROGRESS"}
    ]
  },
  "result_json": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### PATCH /api/v1/tasks/{task_id}
Update task (e.g., approve, request changes).

**Auth**: Required

**Request**:
```json
{
  "status": "APPROVED",
  "review_comment": "Looks good!"
}
```

#### DELETE /api/v1/tasks/{task_id}
Cancel/delete task.

**Auth**: Required

#### WS /api/v1/tasks/{task_id}/stream
WebSocket for real-time task updates.

**Auth**: Required (via query param `?token=<jwt>`)

**Messages**:
```json
// Server → Client
{"type": "status_change", "status": "EXECUTING"}
{"type": "subtask_update", "subtask_id": 1, "status": "COMPLETED"}
{"type": "log", "message": "Running validation..."}
```

---

### GitHub Connections

#### GET /api/v1/github-connections
List connections.

**Auth**: Required

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "repo_url": "https://github.com/user/repo",
      "local_path": "/data/repos/uuid",
      "last_synced_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /api/v1/github-connections
Add connection.

**Auth**: Required

**Request**:
```json
{
  "repo_url": "https://github.com/user/repo",
  "github_token": "ghp_..."
}
```

**Note**: Token is encrypted at rest. Never returned in responses.

#### POST /api/v1/github-connections/{id}/sync
Trigger repo pull/clone.

**Auth**: Required

**Response**:
```json
{
  "message": "Sync started",
  "job_id": "uuid"
}
```

---

### MCP Connections

#### GET /api/v1/mcp-connections
List connections.

**Auth**: Required

#### POST /api/v1/mcp-connections
Add connection.

**Auth**: Required

**Request**:
```json
{
  "name": "Production Logs",
  "endpoint_url": "https://logs.example.com",
  "api_key": "secret_key"
}
```

**Note**: API key is encrypted at rest.

#### POST /api/v1/mcp-connections/{id}/test
Test connection.

**Auth**: Required

---

### Audit Logs

#### GET /api/v1/audit-logs
Get immutable audit trail.

**Auth**: Required

**Query Params**:
- `task_id` (optional): Filter by task
- `event_type` (optional): Filter by event
- `start_time`, `end_time` (optional): Time range

**Response**:
```json
{
  "items": [
    {
      "id": "uuid",
      "event_type": "task_created",
      "actor": "user",
      "task_id": "uuid",
      "details_json": {},
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "uuid",
      "event_type": "llm_call",
      "actor": "agent",
      "task_id": "uuid",
      "details_json": {
        "provider": "llama",
        "model": "llama-3.1-70b",
        "prompt_tokens": 150,
        "completion_tokens": 200
      },
      "created_at": "2024-01-15T10:30:05Z"
    }
  ]
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "detail": "30 per 1 hour"
}
```

### Common Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `UNAUTHORIZED` | 401 | Invalid or missing JWT |
| `FORBIDDEN` | 403 | Valid auth but no permission |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Rate Limits

| Endpoint | Limit | Scope |
|----------|-------|-------|
| All | 60/min | Per IP |
| POST /chat | 30/hour | Per user |
| POST /tasks | 6/hour | Per user |

**Headers** (when rate limited):
```
Retry-After: 3600
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705312800
```

---

## WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket(
  'wss://devbuddy-backend.fly.dev/api/v1/tasks/{task_id}/stream?token={jwt}'
);
```

### Message Format

All messages are JSON:

```typescript
type Message =
  | { type: 'status_change'; status: TaskStatus }
  | { type: 'subtask_update'; subtask_id: number; status: string }
  | { type: 'log'; message: string; level: 'info' | 'warn' | 'error' }
  | { type: 'error'; message: string }
  | { type: 'complete' };
```

### Example

```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  switch (msg.type) {
    case 'status_change':
      console.log('Task status:', msg.status);
      break;
    case 'log':
      console.log('Agent:', msg.message);
      break;
    case 'complete':
      console.log('Task done!');
      ws.close();
      break;
  }
};
```

---

## SDK / Client Libraries

### JavaScript/TypeScript

```typescript
// Using fetch
const response = await fetch('https://devbuddy-backend.fly.dev/api/v1/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({ message: 'Hello' })
});

// Read SSE stream
const reader = response.body.getReader();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // Parse SSE data
}
```

### Python

```python
import requests

# Regular API call
response = requests.get(
    'https://devbuddy-backend.fly.dev/api/v1/tasks',
    headers={'Authorization': f'Bearer {token}'}
)
tasks = response.json()

# SSE stream
import sseclient

response = requests.post(
    'https://devbuddy-backend.fly.dev/api/v1/chat',
    headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'text/event-stream'
    },
    json={'message': 'Hello'},
    stream=True
)

client = sseclient.SSEClient(response)
for event in client.events():
    data = json.loads(event.data)
    print(data)
```

---

## Testing with curl

```bash
# Set your token
TOKEN="your-supabase-jwt"

# Health check (no auth)
curl https://devbuddy-backend.fly.dev/health

# List tasks
curl -H "Authorization: Bearer $TOKEN" \
  https://devbuddy-backend.fly.dev/api/v1/tasks

# Create task
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Test task"}' \
  https://devbuddy-backend.fly.dev/api/v1/tasks

# Chat (SSE stream)
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}' \
  https://devbuddy-backend.fly.dev/api/v1/chat
```

---

*End of API Reference*
