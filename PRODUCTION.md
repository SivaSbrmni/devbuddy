# DevBuddy Production Deployment Guide

This guide covers deploying DevBuddy to the free tier stack:
- **Frontend**: Cloudflare Pages (free, unlimited bandwidth)
- **Backend**: Fly.io (free tier: 3 shared-cpu-1x 256MB VMs + 3GB volume)
- **Database**: Supabase Postgres (free tier: 500MB storage)

---

## Quick Summary

```
1. Push to main → Auto-deploys to production
2. Frontend: https://devbuddy.pages.dev
3. Backend:  https://devbuddy-backend.fly.dev
4. Database: Supabase (already set up)
```

---

## One-Time Setup

### 1. Cloudflare Pages (Frontend)

1. Go to https://dash.cloudflare.com
2. **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
3. Select your repo, framework preset: `None`
4. Skip the Pages dashboard build — we use GitHub Actions
5. Get your credentials:
   - **Account ID**: Workers & Pages sidebar → Account details
   - **API Token**: My Profile → API Tokens → Create Token (use "Cloudflare Pages" template)

Add to GitHub Secrets:
```
CLOUDFLARE_ACCOUNT_ID = your-account-id
CLOUDFLARE_API_TOKEN  = your-api-token
```

### 2. Fly.io (Backend)

1. Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
2. Login: `fly auth login`
3. Create app (first time only):
   ```bash
   fly launch --name devbuddy-backend --region iad --no-deploy
   ```
4. Create persistent volume (for workspaces/repos):
   ```bash
   fly volumes create devbuddy_data --region iad --size 1
   ```
5. Set secrets:
   ```bash
   fly secrets set DATABASE_URL="postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"
   fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
   fly secrets set SUPABASE_JWT_SECRET="your-supabase-jwt-secret"
   fly secrets set LLM_PROVIDER="llama"
   fly secrets set LLM_API_KEY="your-llama-api-key"  # From https://api.llama.com
   fly secrets set E2B_API_KEY="your-e2b-key"        # Optional, for sandboxed exec
   fly secrets set SENTRY_DSN="..."                  # Optional, for error tracking
   ```

Get Fly API token for GitHub Actions:
```bash
fly tokens create
```

Add to GitHub Secrets:
```
FLY_API_TOKEN = your-fly-token
```

### 3. Supabase (Database)

Already configured with your project:
- Project URL: https://oahumeurdneffekoerqa.supabase.co
- Database: Built-in Postgres with pgvector enabled

Connection strings:
```
# Direct connection
postgresql+asyncpg://postgres:PASSWORD@db.oahumeurdneffekoerqa.supabase.co:5432/postgres

# Connection pooler (recommended for serverless/Fly.io)
postgresql+asyncpg://postgres.oahumeurdneffekoerqa:PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

### 4. GitHub Repository Secrets

Navigate to Settings → Secrets → Actions, add:

| Secret | Value | From |
|--------|-------|------|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID | Cloudflare dashboard |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token | Cloudflare dashboard |
| `FLY_API_TOKEN` | Fly.io access token | `fly tokens create` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE PAGES                         │
│                    (Static Hosting - Free)                       │
│                     devbuddy.pages.dev                           │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ API calls
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          FLY.IO                                  │
│               (FastAPI + Alembic + Workspaces)                  │
│              devbuddy-backend.fly.dev (auto-sleep)             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ SQL
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SUPABASE POSTGRES                         │
│                    (500MB Free Tier)                            │
│              pgvector enabled by default                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deploy Workflow

On every push to `main`:

1. **Build** → TypeScript check + Vite build
2. **Deploy Frontend** → Cloudflare Pages
3. **Deploy Backend** → Fly.io (remote Docker build)
4. **Run Migrations** → `alembic upgrade head` inside Fly VM
5. **Smoke Tests** → Verify `/health` endpoints

Manual trigger: Actions tab → Deploy to Production → Run workflow

---

## Local Development

```bash
# Backend
cd backend
cp .env.example .env  # Edit DATABASE_URL, etc.
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head  # Run migrations
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Environment Variables

### Required (all platforms)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Supabase Postgres URL | `postgresql+asyncpg://...` |
| `SECRET_KEY` | Fernet/JWT key (32+ chars) | `openssl rand -hex 32` |
| `SUPABASE_JWT_SECRET` | From Supabase Settings → API | `your-jwt-secret` |
| `LLM_PROVIDER` | `ollama`\|`llama`\|`openai`\|`groq` | `llama` |
| `LLM_API_KEY` | Provider API key | `la-...` |

### Optional

| Variable | Description |
|----------|-------------|
| `E2B_API_KEY` | For sandboxed Python execution |
| `SENTRY_DSN` | Error tracking |
| `TAVILY_API_KEY` | Web search skill |
| `GITHUB_PAT` | Default GitHub token |

---

## Troubleshooting

### Deploy fails

```bash
# Check Fly.io logs
fly logs

# Check deployment status
fly status

# SSH into running VM
fly ssh console
```

### Database migrations fail

```bash
# Run manually
fly ssh console --command "cd /app && alembic upgrade head"

# Check current revision
fly ssh console --command "cd /app && alembic current"
```

### Frontend not connecting to backend

1. Check `VITE_API_BASE_URL` in `wrangler.toml` matches Fly.io URL
2. Verify CORS settings in `backend/app/main.py`
3. Check browser console for network errors

### Rate limiting too aggressive

Edit `backend/app/core/ratelimit.py`:
```python
RATE_GLOBAL = "60/minute"  # Increase from default
```

---

## Security Checklist

- [ ] `SECRET_KEY` is 32+ random characters
- [ ] GitHub tokens encrypted at rest (using Fernet)
- [ ] Rate limiting enabled (`slowapi` middleware)
- [ ] Sandboxed execution configured (`SANDBOX_BACKEND=e2b` or `subprocess`)
- [ ] Database uses Supabase (not exposed to internet)
- [ ] Fly.io VM uses `auto_stop_machines = true` (suspends when idle)

---

## Costs (Free Tier Limits)

| Service | Free Tier | DevBuddy Usage |
|---------|-----------|----------------|
| Cloudflare Pages | 1 build/min, unlimited bandwidth | Frontend hosting |
| Fly.io | 3 VMs (256MB), 3GB volume | 1 backend VM + 1 volume |
| Supabase | 500MB DB, 2GB egress | Postgres + Auth |
| Llama API | 1000 requests/day | LLM calls |

**Estimated monthly cost: $0-2** (if staying within free tier)

---

## Next Steps

1. ✅ Complete one-time setup above
2. ✅ Push this branch to `main`
3. ✅ Verify deploy at https://devbuddy.pages.dev
4. 🔄 Set up custom domain (optional)
5. 🔄 Configure Sentry for error tracking (optional)
6. 🔄 Add e2b.dev API key for secure code execution (optional)
