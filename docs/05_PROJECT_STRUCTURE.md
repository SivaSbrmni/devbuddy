# 05 — Project Structure

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [04_LOCAL_SETUP.md](./04_LOCAL_SETUP.md)

---

## Directory Tree

```
enterprise-agent-platform/
├── AGENT_GUIDE.md           ← Start here for navigation
├── PRODUCTION.md             ← Production deployment guide
├── README.md                 ← High-level project overview
│
├── docs/                     ← Agent documentation
│   ├── 01_PRODUCT_REQUIREMENTS.md
│   ├── 02_ARCHITECTURE_OVERVIEW.md
│   ├── 03_TECHNICAL_SPEC.md
│   ├── 04_LOCAL_SETUP.md
│   ├── 05_PROJECT_STRUCTURE.md  ← You are here
│   ├── 06_AGENT_EXECUTOR.md
│   ├── 07_SECURITY_HARDENING.md
│   ├── 08_DEPLOYMENT.md
│   └── 09_API_REFERENCE.md
│
├── backend/                  ← FastAPI backend
│   ├── app/
│   │   ├── api/              ← API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py       ← Google OAuth, JWT
│   │   │   ├── chat.py       ← Main chat endpoint (SSE)
│   │   │   ├── tasks.py      ← Task CRUD, WebSocket
│   │   │   ├── audit.py      ← Immutable audit log
│   │   │   ├── github_connections.py  ← Encrypted GH tokens
│   │   │   ├── mcp_connections.py       ← Encrypted MCP keys
│   │   │   └── logs.py       ← Query Loki logs
│   │   │
│   │   ├── core/             ← Core utilities
│   │   │   ├── __init__.py
│   │   │   ├── config.py     ← Pydantic settings
│   │   │   ├── database.py   ← SQLAlchemy engine/session
│   │   │   ├── security.py   ← JWT verification
│   │   │   ├── crypto.py     ← NEW: Fernet encryption
│   │   │   ├── ratelimit.py  ← NEW: slowapi config
│   │   │   └── logger.py     ← Loki logging setup
│   │   │
│   │   ├── models/           ← SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── task.py
│   │   │   ├── audit_log.py
│   │   │   ├── github_connection.py
│   │   │   └── mcp_connection.py
│   │   │
│   │   ├── schemas/          ← Pydantic DTOs
│   │   │   ├── __init__.py
│   │   │   ├── task.py
│   │   │   └── ...
│   │   │
│   │   ├── services/         ← Business logic
│   │   │   ├── __init__.py
│   │   │   ├── agent_executor.py  ← ReAct loop core
│   │   │   ├── skills.py          ← @skill decorator + tools
│   │   │   ├── llm_service.py     ← LLM abstraction
│   │   │   └── task_scheduler.py  ← (future: temporal)
│   │   │
│   │   └── main.py           ← FastAPI app factory
│   │
│   ├── alembic/              ← Database migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/                ← Pytest test suite
│   │   ├── __init__.py
│   │   ├── conftest.py       ← Test fixtures
│   │   └── test_smoke.py     ← Basic smoke tests
│   │
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                 ← React frontend
│   ├── src/
│   │   ├── components/       ← Reusable UI components
│   │   │   ├── Layout.tsx
│   │   │   ├── ProtectedRoute.tsx
│   │   │   └── ui/           ← shadcn/ui components
│   │   │
│   │   ├── hooks/            ← Custom React hooks
│   │   │   ├── useAuth.ts
│   │   │   ├── useTasks.ts
│   │   │   └── useWebSocket.ts
│   │   │
│   │   ├── lib/              ← Utilities
│   │   │   ├── api.ts        ← API client
│   │   │   ├── supabase.ts   ← Supabase client
│   │   │   └── utils.ts      ← Helpers
│   │   │
│   │   ├── pages/            ← Route pages
│   │   │   ├── ChatPage.tsx      ← Main interface
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── TasksPage.tsx
│   │   │   ├── AuditPage.tsx
│   │   │   ├── LogsPage.tsx
│   │   │   ├── MCPConnectionsPage.tsx
│   │   │   └── GitHubConnectionsPage.tsx
│   │   │
│   │   ├── App.tsx           ← Router setup
│   │   └── main.tsx          ← Entry point
│   │
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts      ← Vitest test config
│   └── .env.example
│
├── mcp-server/               ← MCP log query server
│   └── server.py             ← 5 MCP tools for Loki/backend
│
├── observability/            ← Logging infrastructure
│   ├── loki-config.yml
│   ├── promtail-config.yml
│   └── grafana/
│       └── provisioning/
│
├── nginx/                    ← Nginx config (self-hosted option)
│   └── nginx.conf
│
├── .github/
│   └── workflows/
│       └── deploy.yml        ← Unified deploy pipeline
│
├── fly.toml                  ← Fly.io backend config
├── wrangler.toml             ← Cloudflare Pages config
├── docker-compose.yml        ← Local dev stack
├── docker-compose.prod.yml   ← Self-hosted prod stack
└── .gitignore
```

---

## Key Files for Common Tasks

### Adding a New API Endpoint

1. **Route handler**: `backend/app/api/<new_feature>.py`
2. **Register in**: `backend/app/main.py` → `app.include_router()`
3. **Add rate limit**: Use `@limiter.limit("...")`
4. **Test**: Add test in `backend/tests/`

### Adding a Database Model

1. **Define model**: `backend/app/models/<model>.py`
2. **Import in**: `backend/app/models/__init__.py`
3. **Create migration**: `alembic revision --autogenerate -m "add <model>"`
4. **Apply**: `alembic upgrade head`

### Adding a Skill

1. **Edit**: `backend/app/services/skills.py`
2. **Decorator**: `@skill(description="...", params={...})`
3. **Async function**: Must return `str` or `dict`
4. **Agent can use**: It's automatically registered

### Modifying Frontend Page

1. **Page component**: `frontend/src/pages/<PageName>.tsx`
2. **API calls**: Use `api.get()` / `api.post()` from `lib/api.ts`
3. **State**: React hooks (useState, useEffect)
4. **Styling**: Tailwind classes

### Adding a New Page

1. **Create**: `frontend/src/pages/NewPage.tsx`
2. **Add route**: `frontend/src/App.tsx` → `<Route path="/new-page">`
3. **Add nav**: `frontend/src/components/Layout.tsx` → sidebar

---

## Configuration Files

| File | Purpose |
|------|---------|
| `backend/.env` | Backend secrets (never commit) |
| `frontend/.env.local` | Frontend public vars (never commit) |
| `fly.toml` | Fly.io backend deploy config |
| `wrangler.toml` | Cloudflare Pages deploy config |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `docker-compose.yml` | Local dev services |
| `backend/pytest.ini` | Pytest config |
| `frontend/vitest.config.ts` | Vitest config |

---

## Where Things Live

| Concept | Location |
|---------|----------|
| Auth (JWT verification) | `backend/app/core/security.py` |
| Rate limiting | `backend/app/core/ratelimit.py` + `api/*.py` |
| Token encryption | `backend/app/core/crypto.py` + `api/*_connections.py` |
| Sandboxed exec | `backend/app/services/skills.py` → `run_python` |
| ReAct loop | `backend/app/services/agent_executor.py` |
| LLM abstraction | `backend/app/services/llm_service.py` |
| Task state machine | `backend/app/api/tasks.py` + `services/agent_executor.py` |
| Audit logging | `backend/app/models/audit_log.py` + `api/audit.py` |
| Chat streaming | `backend/app/api/chat.py` → SSE |
| WebSocket updates | `backend/app/api/tasks.py` → WebSocket endpoint |

---

## Important Patterns

### Backend Pattern: Dependency Injection

```python
# backend/app/api/tasks.py
from app.core.database import get_db
from fastapi import Depends

@router.post("/tasks")
async def create_task(db: AsyncSession = Depends(get_db)):
    # db is injected automatically
    pass
```

### Backend Pattern: Rate Limiting

```python
from app.core.ratelimit import limiter, RATE_TASK

@router.post("/tasks")
@limiter.limit(RATE_TASK)
async def create_task(request: Request, ...):
    # Limited to 6/hour per user
    pass
```

### Frontend Pattern: API Client

```typescript
// frontend/src/lib/api.ts
const response = await api.post('/tasks', {
  description: 'Build a form'
});
```

### Frontend Pattern: Protected Route

```typescript
// frontend/src/App.tsx
<Route element={<ProtectedRoute />}>
  <Route path="/chat" element={<ChatPage />} />
</Route>
```

---

## Generated Files (Don't Edit Directly)

| File | Generated By | Regenerate Command |
|------|---------------|-------------------|
| `backend/alembic/versions/*.py` | `alembic revision` | Manual (one-time) |
| `frontend/dist/` | `npm run build` | `npm run build` |
| `__pycache__/` | Python | Automatic |
| `node_modules/` | npm | `npm install` |

---

**Next**: Read [06_AGENT_EXECUTOR.md](./06_AGENT_EXECUTOR.md) for agent core details.
