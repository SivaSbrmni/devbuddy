# 02 — Architecture Overview

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [01_PRODUCT_REQUIREMENTS.md](./01_PRODUCT_REQUIREMENTS.md)

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENT LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │ React 18 + Vite + TailwindCSS + shadcn/ui                              │  │
│  │ • Chat interface with streaming responses                               │  │
│  │ • Task dashboard with status visualization                              │  │
│  │ • Audit log viewer                                                       │  │
│  │ • GitHub/MCP connection management                                       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    │ HTTPS / WebSocket                        │
│                                    ▼                                         │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────┐
│                                API LAYER (FastAPI)                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │ /auth        │ /chat        │ /tasks       │ /audit       │ /logs        │ │
│  │ • Google     │ • SSE stream │ • CRUD       │ • Immutable  │ • Query      │ │
│  │   OAuth      │   responses  │ • WebSocket  │   history    │   Loki       │ │
│  │ • JWT verify │ • Intent     │   streaming  │              │              │ │
│  │              │   routing    │              │              │              │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘ │
│                                    │                                         │
│                                    │ calls                                    │
│                                    ▼                                         │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SERVICE LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                     AGENT EXECUTOR (ReAct Loop)                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │ Decomposer  │→│   Planner   │→│   Executor  │→│   Observer  │   │  │
│  │  │             │  │             │  │             │  │             │   │  │
│  │  │ Breaks user │  │ Orders      │  │ Runs skills │  │ Validates   │   │  │
│  │  │ request into│  │ subtasks    │  │ (parallel)  │  │ & fixes     │   │  │
│  │  │ subtasks    │  │ with deps   │  │             │  │             │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │  │
│  │                                    │                                     │  │
│  │                                    ▼                                     │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │  │
│  │  │                           SKILLS                                   │   │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │   │  │
│  │  │  │read_file │ │write_file│ │run_python│ │web_search│         │   │  │
│  │  │  │          │ │          │ │◄──sandbox│ │          │         │   │  │
│  │  │  │          │ │          │ │ (e2b/sub)│ │          │         │   │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │   │  │
│  │  └─────────────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    │ SQL (asyncpg)                           │
│                                    ▼                                         │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────┐
│                               DATA LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                      SUPABASE POSTGRES                                  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │  │
│  │  │ users       │ │ tasks       │ │ audit_logs  │ │ github_conn │       │  │
│  │  │ (auth)      │ │ (state)     │ │ (immutable) │ │ (encrypted) │       │  │
│  │  ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤       │  │
│  │  │ mcp_conn    │ │ file_changes│ │ llm_logs    │ │             │       │  │
│  │  │ (encrypted) │ │ (diffs)     │ │ (cost)      │ │             │       │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │  │
│  │                                                                         │  │
│  │  pgvector extension enabled (for future semantic search)              │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Chat → Task → Completion

```
User sends message
    │
    ▼
┌─────────────────────────────────────┐
│ POST /api/v1/chat                   │
│ • Authenticate JWT                  │
│ • Rate limit check (30/hr)          │
│ • Classify intent: chat | pipeline  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ If CONVERSATIONAL:                   │
│   Stream direct LLM response         │
│                                      │
│ If PIPELINE:                         │
│   Create task row (status=PENDING)    │
│   Spawn background executor          │
│   Return task_id via SSE             │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ AGENT EXECUTOR (background)         │
│                                      │
│ 1. DECOMPOSE                         │
│    LLM → JSON array of subtasks     │
│    Each: {id, description, deps}    │
│                                      │
│ 2. PLAN                              │
│    Topological sort by deps           │
│    Parallel batches where possible  │
│                                      │
│ 3. EXECUTE                           │
│    For each subtask:                │
│      • Call appropriate skill     │
│      • Log to audit                 │
│      • Update task state            │
│                                      │
│ 4. VALIDATE                          │
│    • Syntax check (language server) │
│    • Test run                       │
│    • Security scan (pattern match)  │
│                                      │
│ 5. HUMAN CHECKPOINT                  │
│    Status → SECURITY_REVIEW or      │
│              HUMAN_REVIEW            │
│    WebSocket notify frontend        │
│                                      │
│ 6. DELIVERY                          │
│    On approval:                     │
│      • Create branch (optional)     │
│      • Commit                       │
│      • Push (if configured)         │
│    Status → COMPLETED               │
└─────────────────────────────────────┘
```

---

## State Machine Detail

```
                    ┌─────────────┐
                    │   PENDING   │
                    │  (created)  │
                    └──────┬──────┘
                           │ automatic
                           ▼
                    ┌─────────────┐
                    │  PLANNING   │
                    │ (LLM plan)  │
                    └──────┬──────┘
                           │ automatic
                           ▼
              ┌─────────────────────────┐
              │   APPROVAL_REQUIRED     │
              │ (waiting for human yes) │
              └─────────────┬───────────┘
                            │ human approves
                            ▼
     ┌────────────────────────────────────────────────────┐
     │                  EXECUTING                          │
     │  Subtasks run here. Each subtask:                 │
     │    • NOT_STARTED → IN_PROGRESS → COMPLETED/FAILED │
     └────────────────────────┬───────────────────────────┘
                              │ automatic
                              ▼
                    ┌─────────────────┐
         ┌─────────│    VALIDATING   │
         │         │  (check output)   │
         │         └────────┬────────┘
         │                  │
         │          ┌───────┴───────┐
         │          │               │
         │          ▼               ▼ fails
         │    ┌─────────┐    ┌───────────┐
         │    │  VALID  │    │  INVALID  │
         │    └────┬────┘    └─────┬─────┘
         │         │               │
         │         │               ▼ retry
         │         │          ┌───────────┐
         │         │          │   FIXING  │
         │         │          │ (1 retry) │
         │         │          └─────┬─────┘
         │         │                │
         │         │                └────────► FAILED (max retries)
         │         │
         │         ▼
         │    ┌───────────────┐
         │    │ SECURITY_REVIEW │
         │    │ (if touches auth) │
         └────┤                   │
              └────────┬──────────┘
                       │
                       ▼
              ┌───────────────┐
              │  HUMAN_REVIEW   │
              │ (show diff)     │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌──────────┐  ┌──────────┐
   │ APPROVE │   │ REQUEST  │  │  CANCEL  │
   │         │   │ CHANGES  │  │          │
   └────┬────┘   └────┬─────┘  └────┬─────┘
        │              │              │
        ▼              │              ▼
   ┌──────────┐        │         ┌──────────┐
   │READY_TO_ │        │         │  FAILED  │
   │  PUSH    │        │         │          │
   └────┬─────┘        │         └──────────┘
        │              │
        │              └────────────────────┐
        │                                     │
        ▼                                     │
   ┌──────────┐                               │
   │ COMPLETED│◄──────────────────────────────┘
   │          │ (request changes loops back)
   └──────────┘

FAILED can be reached from any state via:
  • Guardrail violation (security scan)
  • Max retries exceeded
  • Human cancellation
  • System error (uncaught exception)
```

---

## Key Design Decisions

### Why FastAPI + Async?
- SSE streaming for real-time updates
- WebSocket for task progress
- High concurrency with low memory (Fly.io 256MB VMs)

### Why Supabase?
- Auth built-in (Google OAuth)
- Managed Postgres (no ops overhead)
- pgvector for future semantic search
- Free tier sufficient for MVP

### Why ReAct Pattern?
- Observable intermediate steps
- Retry at granular level (subtask, not full task)
- Human intervention at logical points
- Debuggable — can inspect plan before execution

### Why Not Temporal/Cadence Yet?
- Added complexity not needed for MVP scale
- Phase 2: Add Temporal when hitting 100+ concurrent tasks

---

## Component Interactions

```
Frontend (React)
    │
    ├──► Supabase Auth (JWT)
    │
    ├──► Backend API (FastAPI)
    │       ├──► Agent Executor
    │       │       ├──► LLM Service (OpenAI/Groq/etc)
    │       │       ├──► Skills (file ops, sandbox, search)
    │       │       └──► Database (SQLAlchemy/asyncpg)
    │       │
    │       ├──► GitHub API (via encrypted tokens)
    │       └──► MCP Server (log queries)
    │
    └──► WebSocket (task updates)
```

---

## Security Boundaries

| Boundary | Control |
|----------|---------|
| User ↔ Frontend | HTTPS, CSP headers |
| Frontend ↔ Backend | JWT validation, CORS whitelist |
| Backend ↔ Database | Connection pooling, asyncpg |
| Backend ↔ LLM | API key rotation, rate limits |
| Backend ↔ GitHub | Encrypted tokens (Fernet) |
| Code Execution | Sandboxed (e2b/subprocess) |

---

**Next**: Read [03_TECHNICAL_SPEC.md](./03_TECHNICAL_SPEC.md) for implementation details.
