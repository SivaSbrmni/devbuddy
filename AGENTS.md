# AGENTS.md

## Cursor Cloud specific instructions

DevBuddy Lite is a FastAPI backend + React/Vite frontend monorepo. PostgreSQL with the **pgvector** extension is required.

### Services

| Service | Port | How to start |
|---------|------|--------------|
| PostgreSQL (pgvector) | 5432 | `sudo docker compose up db -d` (from repo root) |
| Backend (Uvicorn) | 8000 | `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| Frontend (Vite) | 3000 | `cd frontend && npm run dev -- --host 0.0.0.0` |

The Vite dev server proxies `/api` to `http://localhost:8000`.

### Docker in Cloud VMs

Docker is not pre-installed. On first setup, install Docker CE and start `dockerd` manually (systemd may not be available). Use `fuse-overlayfs` storage driver and `iptables-legacy`. See the environment setup commit/PR for the exact install commands.

After `docker compose up db`, enable pgvector once per fresh database:

```bash
sudo docker exec workspace-db-1 psql -U devbuddy -d devbuddy -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The backend `lifespan` hook also creates missing tables on startup, but the vector extension must exist first.

### Environment files

- Copy `backend/.env.example` → `backend/.env` for local backend dev.
- Root `.env` is only needed if using `docker compose up` for backend/frontend services (not just `db`).

Minimum `backend/.env` values:

```
DATABASE_URL=postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy
SECRET_KEY=dev-secret-key-32-chars-long!!
ENVIRONMENT=development
```

### PATH

`pip install --user` puts CLI tools (`uvicorn`, `ruff`, `pytest`) in `~/.local/bin`. Add to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Lint / test / build

Matches `.github/workflows/ci.yml`:

```bash
# Backend lint
cd backend && ruff check . --select E,F,W --ignore E501

# Backend tests (needs Postgres; CI uses database `devbuddy_test`)
DATABASE_URL=postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy_test \
  SECRET_KEY=test-secret-32-chars-long-enough! ENVIRONMENT=test \
  ANTHROPIC_API_KEY= LLAMA_API_KEY= pytest tests/ -v --tb=short

# Frontend build (lint may fail: no eslint.config.js in repo yet)
cd frontend && npm run build
```

Create the test database before running pytest:

```bash
sudo docker exec workspace-db-1 psql -U devbuddy -d postgres -c "CREATE DATABASE devbuddy_test;"
```

### Gotchas

- `python` may not exist; use `python3`.
- Frontend ESLint (`npm run lint`) fails because ESLint v9 expects `eslint.config.js` — the repo has no config file yet. `npm run build` works.
- Backend ruff may report pre-existing unused-import warnings; CI uses the same command.
- Google OAuth is required for full login/workspace UI; health checks and API docs work without it.
- LLM API keys are optional for health/UI; required for chat/agent flows.
