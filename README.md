# DevBuddy Enterprise Agent Platform

Production-ready MVP of an Enterprise Autonomous Coding Agent Platform.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + Vite + TailwindCSS + shadcn/ui |
| Auth | Supabase Auth (Google OAuth) |
| Backend | FastAPI + SQLAlchemy async + asyncpg |
| Database | PostgreSQL 16 |
| Logging | Loki + Promtail + Grafana |
| MCP | Python MCP server (queries Loki + backend) |
| Orchestration | Docker Compose |
| Production | Nginx + Let's Encrypt on DevBuddy.org |

---

## Prerequisites

- Docker + Docker Compose
- Node.js 20+
- Python 3.11+
- A Supabase project (free tier works)

---

## 1. Supabase Setup (5 min)

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Authentication → Providers → Google** and enable it
3. Add redirect URLs: `http://localhost:5173` and `https://devbuddy.org`
4. Copy `Project URL` and `anon public` key from **Settings → API**
5. Copy the `JWT Secret` from **Settings → API → JWT Settings**

---

## 2. Local Development

### Configure environment

```bash
# Backend
cp backend/.env backend/.env          # already created, fill in your values
# Edit: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET

# Frontend
# Edit frontend/.env.local: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
```

### Install frontend dependencies

```bash
cd frontend
npm install
```

### Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Run database migrations

```bash
cd backend
alembic upgrade head
```

### Start everything with Docker Compose

```bash
docker compose up --build
```

Services:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin / admin)
- **Loki**: http://localhost:3100

---

## 3. MCP Server Setup (Windsurf)

### Install MCP dependencies

```bash
cd mcp-server
pip install -r requirements.txt
```

### Register in Windsurf

Copy the contents of `mcp_config.json` into your Windsurf MCP configuration (`~/.windsurf/mcp_config.json` or via Settings → MCP Servers).

Available MCP tools:
- `query_logs` — Run arbitrary LogQL queries
- `get_recent_errors` — Fetch recent ERROR entries
- `get_audit_trail` — Browse the immutable audit log
- `get_task_execution_log` — Full trace for a specific task UUID
- `platform_health_summary` — Health check across all services

---

## 4. Production Deployment (DevBuddy.org)

### On your VPS

```bash
# Clone the repo
git clone <repo> /opt/devbuddy
cd /opt/devbuddy

# Create production env file
cp .env.prod.example .env.prod
nano .env.prod   # Fill in all values

# Get SSL certificates
docker run -it --rm -p 80:80 certbot/certbot certonly \
  --standalone -d devbuddy.org -d www.devbuddy.org \
  -d api.devbuddy.org -d logs.devbuddy.org

# Build images
docker compose -f docker-compose.prod.yml build

# Run migrations
docker compose -f docker-compose.prod.yml run --rm backend \
  alembic upgrade head

# Start all services
docker compose -f docker-compose.prod.yml up -d
```

### Subdomains

| Subdomain | Service |
|-----------|---------|
| `devbuddy.org` | React frontend |
| `api.devbuddy.org` | FastAPI backend |
| `logs.devbuddy.org` | Grafana dashboards |

---

## 5. Project Structure

```
enterprise-agent-platform/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, tasks, audit, logs)
│   │   ├── core/         # config, database, logger, security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic DTOs
│   │   ├── services/     # business logic
│   │   └── main.py
│   ├── alembic/          # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/   # Layout, UI primitives
│   │   ├── hooks/        # useAuth, useTasks, useWebSocket
│   │   ├── lib/          # supabase client, api client, utils
│   │   └── pages/        # Login, Dashboard, Tasks, Audit, Logs
│   ├── package.json
│   └── Dockerfile
├── mcp-server/
│   └── server.py         # 5 MCP tools for log/audit querying
├── observability/
│   ├── loki-config.yml
│   ├── promtail-config.yml
│   └── grafana/provisioning/
├── nginx/
│   └── nginx.conf
├── docker-compose.yml         # Local dev
├── docker-compose.prod.yml    # Production
└── mcp_config.json            # Windsurf MCP registration
```

---

## 6. Agent State Machine

```
PENDING → PLANNING → APPROVAL_REQUIRED → EXECUTING
       → VALIDATING → SECURITY_REVIEW → HUMAN_REVIEW
       → READY_TO_PUSH → COMPLETED
       → FAILED / QUARANTINED (from any state)
```

---

## Phase 2 (Deferred)

- Temporal workflow engine
- Kafka/NATS event streaming
- Firecracker VM sandboxes
- OPA policy engine
- Prometheus + Tempo metrics/traces
- Multi-region / dedicated tiers
