# DevBuddy — Agent Navigation Guide

**Single source of truth for AI agents working on this codebase.**

> **Project Intent**: Build an Enterprise Autonomous Coding Agent Platform where users describe tasks in natural language, and an AI agent decomposes, plans, executes, and delivers code with full auditability and human oversight.

---

## Quick Navigation

| Document | Purpose | Read When |
|----------|---------|-----------|
| **[AGENT_GUIDE.md](./AGENT_GUIDE.md)** | You are here — navigation hub | First read |
| **[01_PRODUCT_REQUIREMENTS.md](./docs/01_PRODUCT_REQUIREMENTS.md)** | What we're building and why | Understanding scope |
| **[02_ARCHITECTURE_OVERVIEW.md](./docs/02_ARCHITECTURE_OVERVIEW.md)** | System design, data flow, state machines | Understanding how it works |
| **[03_TECHNICAL_SPEC.md](./docs/03_TECHNICAL_SPEC.md)** | Stack, APIs, security model | Implementation details |
| **[04_LOCAL_SETUP.md](./docs/04_LOCAL_SETUP.md)** | Run locally in 5 minutes | Starting development |
| **[05_PROJECT_STRUCTURE.md](./docs/05_PROJECT_STRUCTURE.md)** | Directory map, file purposes | Finding code |
| **[06_AGENT_EXECUTOR.md](./docs/06_AGENT_EXECUTOR.md)** | ReAct loop, task decomposition, skills | Working on agent core |
| **[07_SECURITY_HARDENING.md](./docs/07_SECURITY_HARDENING.md)** | Encryption, rate limiting, sandboxing | Security-related tasks |
| **[08_DEPLOYMENT.md](./docs/08_DEPLOYMENT.md)** | Production deployment guide | Deploying changes |
| **[09_API_REFERENCE.md](./docs/09_API_REFERENCE.md)** | Endpoint docs for integration | API changes |

---

## Project Intent (TL;DR)

**DevBuddy** is a production-grade autonomous coding agent platform with:

1. **Natural Language → Code**: User describes what they want, agent delivers code
2. **ReAct Loop**: Task decomposition → Planning → Execution → Validation → Human Review
3. **Full Audit Trail**: Immutable logs of every decision, file change, LLM call
4. **Enterprise Security**: Encrypted tokens, rate limiting, sandboxed execution
5. **Human-in-the-Loop**: Security review, human approval before destructive ops

**Target Users**: Engineering teams wanting AI-assisted development with governance.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUDFLARE PAGES                                │
│                           (React + Vite Frontend)                            │
│                              devbuddy.pages.dev                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ HTTPS / WebSocket
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FLY.IO (Backend)                                │
│                         FastAPI + Async SQLAlchemy                           │
│                        ┌─────────────────────────┐                          │
│                        │    Agent Executor       │                          │
│                        │  ┌─────────────────┐   │                          │
│                        │  │  ReAct Loop     │   │                          │
│                        │  │ • Decompose     │   │                          │
│                        │  │ • Plan          │   │                          │
│                        │  │ • Execute       │   │                          │
│                        │  │ • Validate      │   │                          │
│                        │  │ • Fix           │   │                          │
│                        │  └─────────────────┘   │                          │
│                        │  ┌─────────────────┐   │                          │
│                        │  │  Skills         │   │                          │
│                        │  │ • read_file     │   │                          │
│                        │  │ • write_file    │   │                          │
│                        │  │ • run_python    │◄──┼──► Sandboxed (e2b/subprocess)
│                        │  │ • web_search    │   │                          │
│                        │  └─────────────────┘   │                          │
│                        └─────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ SQL (asyncpg)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SUPABASE POSTGRES                                  │
│               (Auth, Task State, Audit Logs, GitHub/MCP Connections)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Critical Implementation Details

### State Machine (Agent Task Lifecycle)

```
PENDING ──► PLANNING ──► APPROVAL_REQUIRED ──► EXECUTING
                                       │
                                       ├──► VALIDATING ──► SECURITY_REVIEW
                                       │                      │
                                       │                      ▼
                                       │                 HUMAN_REVIEW
                                       │                      │
                                       │                      ▼
                                       └──────────────► READY_TO_PUSH ──► COMPLETED

FAILED / QUARANTINED (from any state via guardrails)
```

### Security Model

| Layer | Mechanism |
|-------|-------------|
| Token Storage | Fernet encryption at rest (`backend/app/core/crypto.py`) |
| API Rate Limits | slowapi: 60/min global, 30/hr chat, 6/hr tasks |
| Code Execution | Sandboxed via e2b.dev or subprocess (disabled by default) |
| Auth | Supabase JWT verification |
| DB | Supabase Postgres (no self-hosted DB in prod) |

### Key Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres
SECRET_KEY=32-char-random-string-for-encryption
SUPABASE_JWT_SECRET=from-supabase-dashboard

# LLM (pick one)
LLM_PROVIDER=llama  # or ollama, openai, groq, together
LLM_API_KEY=your-api-key

# Optional
E2B_API_KEY=for-sandboxed-python-execution
SENTRY_DSN=error-tracking
```

---

## For Different Task Types

### Adding a New Skill
1. Read: [06_AGENT_EXECUTOR.md](./docs/06_AGENT_EXECUTOR.md) → Skills section
2. Edit: `backend/app/services/skills.py`
3. Decorator: `@skill(description="...", params={...})`

### Modifying the ReAct Loop
1. Read: [06_AGENT_EXECUTOR.md](./docs/06_AGENT_EXECUTOR.md) → ReAct Loop section
2. Edit: `backend/app/services/agent_executor.py`
3. Key methods: `execute_task`, `_decompose`, `_plan`, `_observe`

### Database Changes
1. Read: [03_TECHNICAL_SPEC.md](./docs/03_TECHNICAL_SPEC.md) → Database
2. Edit model: `backend/app/models/`
3. Generate migration: `alembic revision --autogenerate -m "desc"`
4. Apply: `alembic upgrade head`

### Security-Related Changes
1. Read: [07_SECURITY_HARDENING.md](./docs/07_SECURITY_HARDENING.md)
2. Check: Rate limits, encryption, sandbox status

### Frontend Changes
1. Read: [05_PROJECT_STRUCTURE.md](./docs/05_PROJECT_STRUCTURE.md) → Frontend
2. Stack: React 18 + Vite + Tailwind + shadcn/ui
3. Key: `frontend/src/pages/ChatPage.tsx` is main interface

### Deployment
1. Read: [08_DEPLOYMENT.md](./docs/08_DEPLOYMENT.md)
2. Pushing to `main` triggers: Cloudflare Pages (frontend) + Fly.io (backend) + Alembic migrations

---

## Testing Locally

```bash
# 1. Clone and setup
git clone <repo>
cd enterprise-agent-platform

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Fill in your Supabase creds
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local  # Fill in VITE_* vars
npm run dev

# 4. Access
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**See full details**: [04_LOCAL_SETUP.md](./docs/04_LOCAL_SETUP.md)

---

## Common Pitfalls

1. **Don't use `exec()` directly** — Use sandboxed execution via `run_python` skill
2. **Don't call `Base.metadata.create_all()` in prod** — Use Alembic migrations
3. **Don't store tokens plaintext** — Use `encrypt_secret()` / `decrypt_secret()`
4. **Don't forget rate limits** — Add `@limiter.limit()` to expensive endpoints
5. **Don't commit `.env` files** — They contain secrets

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Supabase over self-hosted Postgres | Free tier, managed, pgvector included |
| Fly.io over GCP VM | Free tier auto-sleep, zero cold start cost |
| Cloudflare Pages over Vercel | Unlimited bandwidth, better for B2B |
| Llama API over Groq | 1000 req/day free, meta-official |
| e2b sandbox over Firecracker | e2b has generous free tier, easier setup |
| Fernet over AES-GCM | Simpler key management, sufficient for tokens |

---

## Need Help?

- **Understanding intent**: Read [01_PRODUCT_REQUIREMENTS.md](./docs/01_PRODUCT_REQUIREMENTS.md)
- **How something works**: Read [02_ARCHITECTURE_OVERVIEW.md](./docs/02_ARCHITECTURE_OVERVIEW.md)
- **Making a change**: Check this guide's "For Different Task Types" section
- **Debugging**: Check `backend/logs/` or Loki at `http://localhost:3100`

---

*Last updated: 2024-05-24*
*Phase: A+B Complete (Security Hardening + Fly.io/Cloudflare Deploy)*
