# 03 — Technical Specification

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md)

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Frontend | React | 18.x | UI framework |
| Frontend | Vite | 5.x | Build tool |
| Frontend | TailwindCSS | 3.x | Styling |
| Frontend | shadcn/ui | latest | Component library |
| Frontend | react-router-dom | 6.x | Routing |
| Backend | Python | 3.11+ | Runtime |
| Backend | FastAPI | 0.111+ | API framework |
| Backend | SQLAlchemy | 2.x | ORM |
| Backend | asyncpg | 0.29+ | Postgres driver |
| Backend | Alembic | 1.13+ | Migrations |
| Backend | slowapi | latest | Rate limiting |
| Backend | cryptography | 42+ | Token encryption |
| Database | PostgreSQL | 15+ | Primary store |
| Database | pgvector | 0.6+ | Vector extension |
| Auth | Supabase Auth | - | OAuth/JWT |
| LLM | OpenAI SDK | 1.30+ | Universal interface |
| Sandbox | e2b | latest | Code execution |
| Deploy | Fly.io | - | Backend hosting |
| Deploy | Cloudflare Pages | - | Frontend hosting |

---

## Database Schema

```sql
-- Core tables (simplified)

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supabase_uid TEXT UNIQUE NOT NULL,  -- from Supabase Auth
    email TEXT NOT NULL,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    tenant_id UUID NOT NULL,
    parent_task_id UUID REFERENCES tasks(id),  -- for subtasks
    
    -- User input
    description TEXT NOT NULL,
    context_json JSONB,  -- files, URLs, etc.
    
    -- State machine
    status TEXT NOT NULL DEFAULT 'PENDING',  -- enum: PENDING, PLANNING, etc.
    
    -- Agent outputs
    plan_json JSONB,       -- decomposed subtasks
    result_json JSONB,     -- final output
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    tenant_id UUID NOT NULL,
    
    event_type TEXT NOT NULL,  -- 'task_created', 'subtask_completed', 'llm_call', etc.
    actor TEXT NOT NULL,       -- 'user', 'system', 'agent'
    
    details_json JSONB,        -- arbitrary event data
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE github_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    tenant_id UUID NOT NULL,
    
    repo_url TEXT NOT NULL,
    github_token TEXT NOT NULL,  -- ENCRYPTED with Fernet
    
    local_path TEXT,  -- where cloned locally
    last_synced_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE mcp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    tenant_id UUID NOT NULL,
    
    name TEXT NOT NULL,
    api_key TEXT NOT NULL,  -- ENCRYPTED with Fernet
    endpoint_url TEXT,
    
    created_at TIMESTAMPTZ DEFAULT now()
);

-- For LLM cost tracking
CREATE TABLE llm_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    tenant_id UUID NOT NULL,
    
    provider TEXT NOT NULL,  -- 'openai', 'groq', 'llama'
    model TEXT NOT NULL,
    
    prompt_tokens INT,
    completion_tokens INT,
    cost_usd DECIMAL(10,6),
    
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for performance
CREATE INDEX idx_tasks_user ON tasks(user_id, created_at DESC);
CREATE INDEX idx_tasks_status ON tasks(status) WHERE status NOT IN ('COMPLETED', 'FAILED');
CREATE INDEX idx_audit_task ON audit_logs(task_id, created_at DESC);
CREATE INDEX idx_llm_task ON llm_logs(task_id);
```

---

## API Endpoints

### Auth
```
GET  /auth/me              → Current user info
POST /auth/callback        → Supabase OAuth callback
```

### Chat
```
POST /chat                 → Main chat endpoint (SSE streaming)
```

### Tasks
```
GET    /tasks              → List user's tasks
POST   /tasks              → Create new task
GET    /tasks/{id}         → Get task details
PATCH  /tasks/{id}         → Update task (e.g., approve)
DELETE /tasks/{id}         → Cancel task
WS     /tasks/{id}/stream  → WebSocket for live updates
```

### GitHub Connections
```
GET    /github-connections        → List connections
POST   /github-connections        → Add connection (token encrypted)
GET    /github-connections/{id}   → Get details
DELETE /github-connections/{id}   → Remove
POST   /github-connections/{id}/sync → Trigger pull
```

### MCP Connections
```
GET    /mcp-connections           → List connections
POST   /mcp-connections           → Add connection (key encrypted)
POST   /mcp-connections/{id}/test → Test connection
```

### Audit & Logs
```
GET /audit-logs          → Immutable audit trail
GET /llm-logs            → LLM call history with costs
GET /health              → Service health
```

---

## Authentication Flow

```
1. User clicks "Sign in with Google"
   │
   ▼
2. Supabase redirects to Google OAuth
   │
   ▼
3. Google returns to /auth/callback?code=...
   │
   ▼
4. Backend exchanges code for Supabase tokens
   │
   ▼
5. Supabase returns: access_token, refresh_token, user
   │
   ▼
6. Frontend stores tokens in localStorage
   │
   ▼
7. Subsequent requests:
   Header: Authorization: Bearer <access_token>
   │
   ▼
8. Backend verifies JWT with SUPABASE_JWT_SECRET
   │
   ▼
9. On verification, extracts user_id, tenant_id, email
```

---

## Rate Limiting

| Endpoint | Limit | Scope |
|----------|-------|-------|
| All endpoints | 60/min | Per IP (global) |
| POST /chat | 30/hour | Per user |
| POST /tasks | 6/hour | Per user |

Implementation: `slowapi` with Redis-backed storage (in-memory for dev).

---

## Token Encryption

**Algorithm**: Fernet (symmetric, AES-128-CBC + HMAC)

```python
# Key derived from SECRET_KEY (first 32 chars, base64 encoded)
from app.core.crypto import encrypt_secret, decrypt_secret

# Encrypt on write
encrypted = encrypt_secret("ghp_supersecrettoken123")
# → "enc::v1::gAAAAABf..."

# Decrypt on use
decrypted = decrypt_secret(encrypted)
# → "ghp_supersecrettoken123"
```

**Fields encrypted**:
- `github_connections.github_token`
- `mcp_connections.api_key`

---

## Sandboxed Execution

**Configuration**: `SANDBOX_BACKEND` env var

| Value | Behavior |
|-------|----------|
| `e2b` | Runs in e2b.dev microVM (isolated) |
| `subprocess` | Runs in local subprocess (dev only) |
| unset/disabled | Returns error "Sandbox disabled" |

**Safety**:
- Network disabled in e2b sandbox
- 30-second timeout
- Memory limit: 128MB
- No filesystem persistence

---

## LLM Provider Abstraction

All providers use OpenAI-compatible interface:

```python
from app.services.llm_service import llm_generate

response = await llm_generate(
    messages=[
        {"role": "system", "content": "You are a coding assistant"},
        {"role": "user", "content": "Write a React form"}
    ],
    temperature=0.7
)
```

**Supported Providers**:
- `ollama` → local Ollama instance
- `llama` → api.llama.com (Meta's official, 1000 req/day free)
- `openai` → OpenAI API
- `groq` → Groq (fast inference)
- `together` → Together.ai

**Configuration**:
```bash
LLM_PROVIDER=llama
LLM_MODEL=llama-3.1-70b
LLM_API_KEY=la-...
```

---

## Error Handling

| Layer | Strategy |
|-------|----------|
| API | Return JSON: `{"error": "...", "code": "..."}` |
| Agent | Catch → Log → Retry (max 1) → Human review |
| Database | SQLAlchemy exceptions → 500 with safe message |
| External APIs | Circuit breaker pattern (timeout 30s) |

**Sentry Integration**: `SENTRY_DSN` env var enables automatic error reporting.

---

## Environment Variables

### Required
```bash
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=32-char-random-string
SUPABASE_JWT_SECRET=from-supabase-dashboard
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### LLM (pick one provider)
```bash
LLM_PROVIDER=llama|ollama|openai|groq|together
LLM_MODEL=llama-3.1-70b|llama3.2:latest|gpt-4|...
LLM_API_KEY=sk-...  # not needed for ollama
```

### Optional
```bash
E2B_API_KEY=for-sandboxed-execution
SENTRY_DSN=error-tracking
TAVILY_API_KEY=for-web-search
GITHUB_PAT=default-github-token
SANDBOX_BACKEND=e2b|subprocess
```

---

## Migration Strategy

**Never use `Base.metadata.create_all()` in production.**

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "add user table"

# Apply locally
alembic upgrade head

# Apply in production (via CI/CD)
flyctl ssh console --command "cd /app && alembic upgrade head"
```

---

**Next**: Read [04_LOCAL_SETUP.md](./04_LOCAL_SETUP.md) to run locally.
