# DevBuddy — Agent Reference Document

> **Last updated:** 2026-06-15  
> **Purpose:** Single source of truth for any AI agent working on this codebase. **Update this file after every meaningful change.**

---

## 1. Project Overview

**DevBuddy** is an autonomous software engineering platform. It provides:

- **AI-powered chat interface** with live model selection and streaming responses
- **Autonomous pipeline**: Requirements → Analysis → Planning → Architecture → Coding → Review → Testing
- **Multi-agent orchestration** using specialized AI agents (Requirement Analyzer, Planner, Architect, Coder, Reviewer, Tester, Deployment Agent)
- **Model routing** with tiered LLM selection (cheap models for drafts, Claude for engineering tasks)
- **Workspace management** with file system access and command execution
- **Deployment automation** to Railway, Vercel, or Docker
- **Google OAuth authentication** with invite-only email allowlist

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI 0.115, Uvicorn, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| **Database** | PostgreSQL 16 with pgvector extension |
| **LLM Providers** | Anthropic (Claude), Llama API, Ollama |
| **Auth** | Google OAuth2 + JWT (python-jose) |
| **Frontend** | React 19, TypeScript, Vite 6, react-router-dom |
| **Styling** | Inline styles (no CSS framework) — dark theme (#0d0f14 base) |
| **Deployment** | HuggingFace Space (backend), GitHub Pages (frontend) |
| **Local Dev** | Docker Compose (db + backend + frontend) |

---

## 3. Project Structure

```
devbuddy/
├── .github/workflows/         # CI/CD pipelines
│   ├── ci.yml                  # Lint, test, frontend build
│   └── deploy-pages.yml        # Deploy frontend to GitHub Pages
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint — routers, CORS, SPA fallback
│   │   ├── api/routes/         # HTTP route handlers
│   │   │   ├── auth.py         # Google OAuth + JWT endpoints
│   │   │   ├── models.py       # Live model listing (Ollama + Claude)
│   │   │   ├── chat.py         # Streaming chat SSE endpoint
│   │   │   ├── projects.py     # Project CRUD + pipeline triggers
│   │   │   ├── execution.py    # Task execution endpoints
│   │   │   ├── memory.py       # Project memory/context endpoints
│   │   │   ├── workspace.py    # Workspace file/command operations
│   │   │   ├── skills.py       # Agent skills registry
│   │   │   ├── metrics.py      # Dashboard metrics
│   │   │   └── health.py       # Health check
│   │   ├── agents/             # Autonomous AI agents
│   │   │   ├── base.py         # BaseAgent — LLM access, step tracking
│   │   │   ├── orchestrator.py # TaskOrchestrator — coordinates all agents
│   │   │   ├── requirement_analyzer.py
│   │   │   ├── planner.py
│   │   │   ├── architect.py
│   │   │   ├── coder.py
│   │   │   ├── reviewer.py
│   │   │   ├── tester.py
│   │   │   ├── deployment_agent.py
│   │   │   ├── fix_agent.py
│   │   │   ├── improvement_agent.py
│   │   │   └── execution_controller.py
│   │   ├── core/
│   │   │   ├── config.py       # Settings (env vars, pydantic-settings)
│   │   │   ├── model_router.py # LLM provider routing + cost tracking
│   │   │   ├── deps.py         # FastAPI dependencies (get_db)
│   │   │   └── logging.py      # Structlog setup
│   │   ├── db/
│   │   │   ├── base.py         # SQLAlchemy Base
│   │   │   ├── session.py      # Async engine + session factory
│   │   │   └── base.py         # Alembic target metadata
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── project.py      # Project, relationships
│   │   │   ├── task.py         # Task, Milestone, AgentStep
│   │   │   ├── execution.py    # Run, ExecutionLog
│   │   │   └── memory.py       # ProjectMemory
│   │   ├── schemas/
│   │   │   └── project.py      # Pydantic request/response schemas
│   │   ├── memory/
│   │   │   └── manager.py      # MemoryManager — store/recall project context
│   │   ├── execution/
│   │   │   └── github_actions.py # GitHub Actions client
│   │   ├── browser/
│   │   │   └── agent.py        # Browser automation agent
│   │   ├── deployment/
│   │   ├── improvement/
│   │   ├── knowledge/
│   │   ├── observability/
│   │   ├── repair/
│   │   ├── security/
│   │   ├── skills/
│   │   └── workspace/
│   ├── static/                 # Built frontend (served by FastAPI SPA fallback)
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Root router — hostname-based routing
│   │   ├── main.tsx            # React entrypoint
│   │   ├── api/client.ts       # HTTP client wrapper
│   │   ├── context/
│   │   │   └── AuthContext.tsx # Auth state, token handling, user info
│   │   ├── components/
│   │   │   └── Layout.tsx
│   │   └── pages/
│   │       ├── LandingPage.tsx # Marketing landing page
│   │       ├── ChatPage.tsx    # Main chat UI (Devin-style)
│   │       ├── LoginGate.tsx   # Auth gate — Google sign-in screen
│   │       ├── ProjectsPage.tsx
│   │       ├── ProjectDetailPage.tsx
│   │       ├── DashboardPage.tsx
│   │       ├── WorkspacePage.tsx
│   │       ├── MetricsPage.tsx
│   │       ├── SkillsPage.tsx
│   │       └── KnowledgePage.tsx
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── Dockerfile
├── deploy/
│   ├── Dockerfile               # HuggingFace Space production image
│   ├── start.sh                 # Starts embedded PostgreSQL + FastAPI
│   └── README.md
├── docker-compose.yml           # Local dev: db + backend + frontend
├── .env.example
└── agent.md                     # ← THIS FILE
```

---

## 4. Backend Architecture

### 4.1 FastAPI Application (`app/main.py`)

- **Lifespan**: initializes logging, creates DB tables, starts model_router, github_client, browser_agent
- **CORS**: allows `localhost:5173/3000`, `devbuddy.org`, `dev.devbuddy.org`, `sivasbrmni-devbuddy.hf.space`
- **Router registration**:
  - `health_router` — no prefix
  - All others prefixed with `/api/v1`
- **SPA fallback**: any non-API route serves `static/index.html`

### 4.2 Configuration (`app/core/config.py`)

Loaded from environment variables via `pydantic-settings`. Key settings:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | JWT signing | `change-me-in-production-32-chars!` |
| `DATABASE_URL` | PostgreSQL async connection | `postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy` |
| `API_PREFIX` | API route prefix | `/api/v1` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude LLM | — |
| `LLAMA_API_KEY` / `LLAMA_MODEL` / `LLAMA_API_BASE` | Llama API | — |
| `OLLAMA_API_KEY` / `OLLAMA_MODEL` / `OLLAMA_API_BASE` | Ollama cloud | — |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth credentials | — |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/api/v1/auth/google/callback` |
| `FRONTEND_URL` | Where to redirect after login | Derived from `GOOGLE_REDIRECT_URI` |
| `ALLOWED_EMAILS` | Comma-separated invite list | `sivasbrmni@gmail.com` |
| `GITHUB_TOKEN` / `GITHUB_DEFAULT_ORG` | GitHub Actions integration | — |
| `RAILWAY_TOKEN` / `VERCEL_TOKEN` | Deployment providers | — |

**Properties:**
- `frontend_url` — returns `FRONTEND_URL` if set, otherwise derives from redirect URI
- `allowed_emails_set` — parses `ALLOWED_EMAILS` into lowercase set

### 4.3 Authentication (`app/api/routes/auth.py`)

Endpoints (all under `/api/v1/auth`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/google/login` | GET | Redirects to Google consent screen |
| `/google/callback` | GET | Exchanges code for tokens, validates email, creates JWT, redirects to frontend with `?token={jwt}` |
| `/me` | GET | Validates JWT from query param, returns `{email, name, picture}` |
| `/logout` | GET | Clears cookie, redirects to `/` |

### 4.4 Models API (`app/api/routes/models.py`)

Endpoints (under `/api/v1`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/models` | GET | Returns live model list from Ollama + Claude with `{id, label, provider, family}` |

### 4.5 Chat API (`app/api/routes/chat.py`)

Endpoints (under `/api/v1`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Streaming chat via SSE. Accepts `{messages: [{role, content}], model}`. Returns `data: {chunk}` stream.

**Flow:**
1. Frontend calls `window.location.href = {BACKEND}/api/v1/auth/google/login`
2. User authenticates with Google
3. Google redirects to `{BACKEND}/api/v1/auth/google/callback?code=...`
4. Backend exchanges code for access token
5. Backend fetches user info from Google
6. Backend validates email against `allowed_emails_set`
7. Backend creates JWT (HS256, expires in 24h)
8. Backend redirects to `{FRONTEND_URL}/app?token={jwt}`
9. Frontend reads token from URL, stores in `localStorage`, fetches `/me`

### 4.6 Model Router (`app/core/model_router.py`)

- **ModelTier**: `DRAFT` (Llama — cheap, fast) vs `ENGINEER` (Claude — precise)
- **TaskCategory**: 18 categories mapped to tiers
- **Providers**: anthropic, llama, ollama with fallback chains
- **Cost tracking**: per-request cost estimation based on token counts
- **Singleton**: `model_router` instantiated once at app startup

### 4.7 Agents (`app/agents/`)

All agents inherit from `BaseAgent`:

- `run(task_id, context)` — entry point, handles logging and step tracking
- `execute(context)` — abstract method, implemented by each agent
- `llm(messages, category, ...)` — calls model router with task category

**Orchestrator Pipeline:**
1. `RequirementAnalyzer` → structured specification
2. `Planner` → implementation plan with milestones
3. `Architect` → system architecture
4. `Coder` → code generation
5. `Reviewer` → code review (Engineering Review Gateway)
6. `Tester` → test generation

### 4.8 Database Models

**Project** (`app/models/project.py`):
- `id: UUID` — primary key
- `name, description, repo_url, repo_branch`
- `status: Enum(active|paused|completed|archived)`
- `tech_stack: JSONB`, `config: JSONB`
- Relationships: tasks, milestones, runs, memories

**Task** (`app/models/task.py`):
- `id, project_id, title, description, task_type, status, priority`
- `context: JSONB`, `result: JSONB`, `retry_count`
- Relationships: project, milestone, parent task, agent_steps

**ProjectMemory** (`app/models/memory.py`):
- `id, project_id, category, title, content, metadata_: JSONB`
- Used by `MemoryManager` to build project context strings

---

## 5. Frontend Architecture

### 5.1 Routing (`frontend/src/App.tsx`)

**Hostname-based routing** (critical for GitHub Pages single-domain limitation):

- `dev.devbuddy.org` → Chat app at `/`
- `sivasbrmni-devbuddy.hf.space` → Chat app at `/`
- `devbuddy.org` → Landing page at `/`, Chat app at `/app`

All chat routes wrapped in `AuthProvider` → `LoginGate`.

### 5.2 Authentication Context (`frontend/src/context/AuthContext.tsx`)

- Reads `?token=` from URL on mount → stores in `localStorage`
- Fetches `/api/v1/auth/me?token={stored}` to validate and get user info
- `login()` → redirects to backend Google OAuth endpoint
- `logout()` → clears `localStorage`, redirects to `/`

### 5.3 API Client (`frontend/src/api/client.ts`)

Simple fetch wrapper around `{VITE_API_URL}/api/v1`. Functions for:
- Projects (list, get, create, delete)
- Pipeline (run, coding task)
- Tasks, Memory, Skills, Workspace, Metrics, Deploy, Repair

### 5.4 Chat Page (`frontend/src/pages/ChatPage.tsx`)

Devin-style chat UI:
- Left sidebar: conversation list, new chat button, user info with logout
- Main area: message history with user/assistant bubbles, model selector
- Input: auto-resizing textarea, Enter to send, Shift+Enter for newline
- Conversations stored in `localStorage` (`devbuddy_convs`)
- **Live model fetching**: Calls `/api/v1/models` on mount to populate model dropdown
- **Streaming responses**: Uses SSE to stream chat responses from `/api/v1/chat`

### 5.5 Login Gate (`frontend/src/pages/LoginGate.tsx`)

- Shows loading spinner while auth state initializes
- If not authenticated: shows branded sign-in screen with Google OAuth button
- If authenticated: renders children (chat app)

---

## 6. Deployment Setup

### 6.1 HuggingFace Space (Backend)

- **Space**: `Sivasbrmni/devbuddy`
- **URL**: `https://sivasbrmni-devbuddy.hf.space`
- **Type**: Docker (custom `deploy/Dockerfile` + `deploy/start.sh`)
- **Port**: 7860 (HuggingFace default, mapped internally)
- **Database**: Embedded PostgreSQL 16 with pgvector, initialized in `start.sh`

**Environment Variables (set in HuggingFace UI):**

| Variable | Value | Type |
|----------|-------|------|
| `GOOGLE_CLIENT_ID` | `<YOUR_GOOGLE_CLIENT_ID>` | Secret |
| `GOOGLE_CLIENT_SECRET` | `<YOUR_GOOGLE_CLIENT_SECRET>` | Secret |
| `GOOGLE_REDIRECT_URI` | `https://sivasbrmni-devbuddy.hf.space/api/v1/auth/google/callback` | Variable |
| `FRONTEND_URL` | `https://sivasbrmni-devbuddy.hf.space` | Variable |
| `SECRET_KEY` | `<YOUR_SECRET_KEY>` | Secret |
| `ALLOWED_EMAILS` | `sivasbrmni@gmail.com` | Variable |
| `ANTHROPIC_API_KEY` | (user's key) | Secret |
| `OLLAMA_API_KEY` | (user's key) | Secret |
| `GITHUB_TOKEN` | (user's token) | Secret |

**Auto-deployment:** The HuggingFace Space auto-syncs with GitHub via `.github/workflows/deploy-hf-space.yml`. When you push to `main` with backend changes, the workflow:
1. Pushes to the HF Space git repository
2. Syncs `OLLAMA_API_KEY` from GitHub secrets to HF Space secrets
3. Waits for the Space to rebuild
4. Runs a smoke test on `/health`

### 6.2 GitHub Pages (Frontend)

- **Repository**: `SivaSbrmni/devbuddy`
- **Custom Domain**: `devbuddy.org`
- **CNAME**: `devbuddy.org` (set in `deploy-pages.yml`)
- **404 Handling**: `dist/404.html` copied from `index.html` for SPA routing

**Build env**: `VITE_API_URL=https://sivasbrmni-devbuddy.hf.space`

### 6.3 Google OAuth Configuration

- **Project**: `fine-eye-378306` in Google Cloud Console
- **Redirect URIs**: 
  - `https://sivasbrmni-devbuddy.hf.space/api/v1/auth/google/callback` (production)
  - `http://localhost:8000/api/v1/auth/google/callback` (local dev)
- **JavaScript Origin**: `https://dev.devbuddy.org`
- **Test users**: Must add emails manually in Console → Audience → Test users

---

## 7. Local Development

### 7.1 Docker Compose (Recommended)

```bash
docker-compose up --build
```

Services:
- **db**: PostgreSQL 16 + pgvector on port 5432
- **backend**: FastAPI on port 8000
- **frontend**: Vite dev server on port 3000 (proxies `/api` to backend)

### 7.2 Manual (Backend only)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit as needed
uvicorn app.main:app --reload --port 8000
```

### 7.3 Manual (Frontend only)

```bash
cd frontend
npm install
npm run dev  # port 3000, proxies /api to localhost:8000
```

---

## 8. CI/CD Pipelines

### 8.1 CI (`ci.yml`)

Runs on push/PR to `main`:
1. **Lint** — ruff check backend
2. **Test** — pytest with PostgreSQL service container
3. **Frontend Build** — `npm install && npm run build`

### 8.2 Deploy to GitHub Pages (`deploy-pages.yml`)

Runs on push to `main` when `frontend/**` changes:
1. Build frontend with `VITE_API_URL=https://sivasbrmni-devbuddy.hf.space`
2. Set `CNAME` to `devbuddy.org`
3. Copy `index.html` to `404.html`
4. Deploy to GitHub Pages

---

## 9. Common Issues & Solutions

| Issue | Cause | Fix |
|-------|-------|-----|
| Auth routes 404 on HuggingFace | `auth.py` not deployed to Space | Upload `auth.py` to Space via HuggingFace UI |
| Redirect goes to backend URL | `FRONTEND_URL` not set | Set `FRONTEND_URL=https://devbuddy.org` in Space settings |
| "Access denied: not on invite list" | Email not in `ALLOWED_EMAILS` | Add email to `ALLOWED_EMAILS` env var |
| Google OAuth error: redirect_uri_mismatch | URI not registered in Google Console | Add exact callback URI to Google Console credentials |
| Space shows "Runtime error" | Import error in startup | Check container logs for missing files/deps |
| Frontend 404 on `/app` | GitHub Pages doesn't support SPA routing | Ensure `404.html` is deployed alongside `index.html` |
| CORS errors | Origin not in backend CORS list | Add origin to `allow_origins` in `main.py` |

---

## 10. How to Update This Document

**Rule: Every meaningful code change must be reflected here.**

When you make changes, update the relevant section(s) above. Specifically:

- **New env var** → Update Section 4.2 (Config) and 6.1 (Deployment)
- **New API endpoint** → Update Section 4.3 (Auth) or add to route table
- **New route file** → Update Section 3 (Structure) and 4.1 (Routers)
- **New agent** → Update Section 4.5 (Agents)
- **New frontend page** → Update Section 3 (Structure) and 5 (Frontend)
- **Auth flow changes** → Update Section 4.3 (Auth) and 5.2 (AuthContext)
- **Deployment changes** → Update Section 6 (Deployment)
- **Dependency changes** → Update Section 2 (Tech Stack)

**After updating, change the "Last updated" date at the top.**

---

## 11. Quick Reference

### 11.1 Key File Paths

| Concept | File |
|---------|------|
| FastAPI entry | `backend/app/main.py` |
| Config / env vars | `backend/app/core/config.py` |
| Auth routes | `backend/app/api/routes/auth.py` |
| Model router | `backend/app/core/model_router.py` |
| Orchestrator | `backend/app/agents/orchestrator.py` |
| React entry | `frontend/src/main.tsx` |
| React router | `frontend/src/App.tsx` |
| Auth context | `frontend/src/context/AuthContext.tsx` |
| API client | `frontend/src/api/client.ts` |
| Chat UI | `frontend/src/pages/ChatPage.tsx` |
| Login screen | `frontend/src/pages/LoginGate.tsx` |
| CI pipeline | `.github/workflows/ci.yml` |
| Pages deploy | `.github/workflows/deploy-pages.yml` |
| Space startup | `deploy/start.sh` |
| Space Dockerfile | `deploy/Dockerfile` |

### 11.2 API Prefixes

- Health: `/health`
- All others: `/api/v1/{resource}`
- Auth: `/api/v1/auth/google/login`, `/api/v1/auth/google/callback`, `/api/v1/auth/me`

### 11.3 Environment Files

- `backend/.env.example` — template for local dev
- `frontend/.env` — not in repo; set `VITE_API_URL` for local dev
- HuggingFace Space — set via UI: Settings → Variables & Secrets

---

*End of document. Keep this accurate and it will keep agents productive.*

### 11.4 Known Issues & Recent Fixes

- **Cloud-agent branch collisions** — `backend/app/agents/cloud_runner.py` now checks
  whether a semantic branch already exists and appends a counter (`-2`, `-3`, etc.)
  before creating the GitHub ref, preventing `422 Reference already exists` failures.

- **Empty assistant bubble for cloud-agent tasks** — `frontend/src/pages/Workspace.tsx`
  now preserves `taskCard` metadata when server-syncing messages and writes cloud-agent
  error payloads into the assistant message content so failures are visible.

- **Frontend API URL in production builds** — `frontend/vite.config.ts` explicitly defines
  `import.meta.env.VITE_API_URL` via `loadEnv(mode, process.cwd(), '')`. This prevents
  stale `.env.production` files from overriding the CI-provided backend URL.

- **GitHubPanel repo stats crash** — `frontend/src/components/GitHubPanel.tsx` guards
  `stargazers_count`, `forks_count`, `open_issues_count`, and `default_branch` against
  undefined values.


### 11.5 LLM Provider Routing

- **Universal provider table**: `backend/app/models/llm_provider.py` (`user_llm_providers`)
- **Provider settings UI**: `frontend/src/components/LLMProviderSettings.tsx` +
  `frontend/src/hooks/useLLMProviders.ts`
- **Chat endpoint**: `backend/app/api/routes/chat.py` now authenticates the user,
  loads providers from `user_llm_providers`, and falls back to legacy
  `UserSettings.api_keys` (anthropic/ollama/llama) when the new table is empty.
- **Provider test endpoint**: `backend/app/api/routes/llm_providers.py` tests
  `/models` or `/v1/models` depending on whether the base URL already ends in `/v1`.

