# 04 — Local Development Setup

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [03_TECHNICAL_SPEC.md](./03_TECHNICAL_SPEC.md)

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Node.js | 20+ | `node --version` |
| Python | 3.11+ | `python --version` |
| Git | any | `git --version` |
| Docker | (optional) | `docker --version` |

---

## Step-by-Step Setup

### 1. Clone & Navigate

```bash
cd C:\Users\sivas\CascadeProjects\enterprise-agent-platform
```

### 2. Supabase Setup (Required)

1. Go to https://supabase.com and create a project (free tier)
2. Go to **Authentication → Providers → Google** and enable it
3. Add redirect URLs:
   - `http://localhost:5173` (dev)
   - `https://your-production-domain.com` (later)
4. Get credentials from **Settings → API**:
   - `Project URL` (like `https://xxx.supabase.co`)
   - `anon public` key
   - `JWT Secret` (from JWT Settings section)
5. Database connection: Get from **Database → Connection String** → URI tab

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (choose your OS)
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
```

Edit `.env`:
```bash
ENVIRONMENT=development
SECRET_KEY=dev-secret-key-at-least-32-chars-long!!!

# Supabase
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# LLM (choose one)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:latest
# LLM_API_KEY=not-needed-for-ollama

# Optional
E2B_API_KEY=your-e2b-key
SENTRY_DSN=
```

**For Ollama (local LLM)**:
```bash
# Install ollama from https://ollama.com
# Pull a model:
ollama pull llama3.2:latest

# In a separate terminal, keep ollama running:
ollama serve
```

**Run database migrations**:
```bash
cd backend
alembic upgrade head
```

**Start backend**:
```bash
uvicorn app.main:app --reload --port 8000
```

Backend is now running at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env.local
```

Edit `.env.local`:
```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

**Start frontend**:
```bash
npm run dev
```

Frontend is now running at: http://localhost:5173

### 5. Verify Setup

1. Open http://localhost:5173
2. Click "Sign in with Google"
3. Complete OAuth flow
4. You should see the Chat interface
5. Type a message → Should get response from local Ollama (or configured LLM)

---

## Running with Docker Compose (Alternative)

If you prefer Docker over local Python/Node:

```bash
# In project root
cp .env.example .env  # Fill as above

# Start all services (includes Postgres, Loki, Grafana locally)
docker-compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Grafana: http://localhost:3000 (admin/admin)
- Loki: http://localhost:3100

**Note**: This uses local Postgres, not Supabase. Good for offline dev.

---

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'app'`
**Fix**: Make sure you're in the `backend` directory when running uvicorn.

### Issue: `alembic command not found`
**Fix**: Ensure virtual environment is activated and run:
```bash
pip install alembic
```

### Issue: CORS errors in browser
**Fix**: Check `VITE_API_BASE_URL` points to `http://localhost:8000` (not https).

### Issue: Supabase auth fails
**Fix**: 
1. Verify `SUPABASE_JWT_SECRET` matches Supabase dashboard
2. Check redirect URLs include `http://localhost:5173`

### Issue: LLM not responding
**Fix**:
- For Ollama: Check `ollama serve` is running
- For cloud providers: Verify `LLM_API_KEY` is set

---

## Development Workflow

### Making Backend Changes

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate

# Edit code...

# Restart server (if not using --reload)
# uvicorn auto-reloads on file changes

# Run migrations after model changes
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Making Frontend Changes

```bash
cd frontend

# Edit code...
# Vite auto-reloads on file changes
```

### Testing API Endpoints

Use the auto-generated docs:
1. Open http://localhost:8000/docs
2. Click "Authorize" and enter your JWT (get from browser localStorage after login)
3. Test endpoints interactively

---

## File Watchers & Hot Reload

| Service | Auto-reload | Trigger |
|---------|-------------|---------|
| Backend (uvicorn) | Yes | File change |
| Frontend (Vite) | Yes | File change |
| Docker Compose | No | Manual restart |

---

## Stopping Services

```bash
# Backend: Ctrl+C in terminal
# Frontend: Ctrl+C in terminal

# Docker Compose:
docker-compose down

# Remove volumes (database data):
docker-compose down -v
```

---

**Next**: Read [05_PROJECT_STRUCTURE.md](./05_PROJECT_STRUCTURE.md) to understand the codebase.
