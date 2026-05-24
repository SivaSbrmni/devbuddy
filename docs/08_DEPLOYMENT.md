# 08 — Deployment Guide

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [07_SECURITY_HARDENING.md](./07_SECURITY_HARDENING.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLOUDFLARE PAGES                           │
│                  (Frontend - Free Tier)                         │
│                     devbuddy.pages.dev                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FLY.IO                                   │
│                  (Backend - Free Tier)                          │
│               devbuddy-backend.fly.dev                          │
│                                                                  │
│  • Auto-sleep after 5 min idle (free tier)                      │
│  • Auto-wake on request (cold start ~2s)                        │
│  • 256MB RAM, 1 shared CPU                                     │
│  • 1GB persistent volume for workspaces                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQL
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SUPABASE POSTGRES                             │
│                   (Database - Free Tier)                         │
│            500MB storage, pgvector enabled                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## One-Time Setup

### 1. Supabase (Already Done)

Your project is already configured:
- URL: `https://oahumeurdneffekoerqa.supabase.co`
- Database: Postgres with pgvector

Get connection strings:
1. Supabase Dashboard → Database → Connection String
2. Copy the URI format

### 2. Cloudflare Pages (Frontend)

**Step 1**: Get credentials
1. Go to https://dash.cloudflare.com
2. **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
3. Select your GitHub repo
4. Framework preset: `None` (we build in CI)

**Step 2**: Get API credentials
- **Account ID**: Right sidebar in Workers & Pages
- **API Token**: My Profile → API Tokens → Create Token
  - Template: "Cloudflare Pages"
  - Permissions: Zone:Read, Page Rules:Edit, Cloudflare Pages:Edit

**Step 3**: Add GitHub secrets
```
CLOUDFLARE_ACCOUNT_ID = your-account-id
CLOUDFLARE_API_TOKEN = your-api-token
```

### 3. Fly.io (Backend)

**Step 1**: Install flyctl
```bash
# macOS
brew install flyctl

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# Linux
curl -L https://fly.io/install.sh | sh
```

**Step 2**: Login
```bash
fly auth login
```

**Step 3**: Create app (first time only)
```bash
fly launch --name devbuddy-backend --region iad --no-deploy
```

**Step 4**: Create persistent volume
```bash
fly volumes create devbuddy_data --region iad --size 1
```

**Step 5**: Set secrets
```bash
fly secrets set DATABASE_URL="postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"
fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
fly secrets set SUPABASE_JWT_SECRET="your-jwt-secret-from-supabase"
fly secrets set SUPABASE_URL="https://oahumeurdneffekoerqa.supabase.co"
fly secrets set SUPABASE_ANON_KEY="your-anon-key"
fly secrets set LLM_PROVIDER="llama"
fly secrets set LLM_API_KEY="your-llama-api-key"
fly secrets set E2B_API_KEY="your-e2b-key"  # Optional
fly secrets set SENTRY_DSN="your-sentry-dsn"  # Optional
```

**Step 6**: Get API token for CI
```bash
fly tokens create
```

Add to GitHub secrets:
```
FLY_API_TOKEN = token-from-above
```

---

## Deploy on Push

The GitHub Actions workflow (`.github/workflows/deploy.yml`) runs on every push to `main`:

```yaml
1. Build Frontend
   └── TypeScript check + Vite build
   
2. Deploy Frontend → Cloudflare Pages

3. Deploy Backend → Fly.io
   └── Remote Docker build
   
4. Run Database Migrations
   └── alembic upgrade head
   
5. Smoke Tests
   └── Verify /health endpoints
```

### Manual Trigger

Go to GitHub → Actions → Deploy to Production → Run workflow

---

## Fly.io Configuration

**File**: `fly.toml`

```toml
app = 'devbuddy-backend'
primary_region = 'iad'

[build]
  dockerfile = 'backend/Dockerfile'

[env]
  ENVIRONMENT = 'production'
  PORT = '8000'

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = 'suspend'  # Free tier: sleep when idle
  auto_start_machines = true       # Wake on request
  min_machines_running = 0         # Can scale to 0

[[http_service.checks]]
  interval = '30s'
  timeout = '5s'
  path = '/health'

[[vm]]
  cpu_kind = 'shared'
  cpus = 1
  memory_mb = 256  # Free tier (can bump to 512 for $2/mo)

[[mounts]]
  source = 'devbuddy_data'
  destination = '/data'  # Persistent storage
```

---

## Cloudflare Pages Configuration

**File**: `wrangler.toml`

```toml
name = "devbuddy"
compatibility_date = "2024-01-01"

[site]
bucket = "./frontend/dist"

[env.production]
  # Build-time env vars (replaced by Vite)
  VITE_SUPABASE_URL = "https://oahumeurdneffekoerqa.supabase.co"
  VITE_SUPABASE_ANON_KEY = "sb_publishable_..."
  VITE_API_BASE_URL = "https://devbuddy-backend.fly.dev"
```

---

## Database Migrations

### Automatic (CI/CD)

Migrations run automatically in the deploy pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Run database migrations
  run: flyctl ssh console --command "cd /app && alembic upgrade head"
  env:
    FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

### Manual

```bash
# Run migrations manually
flyctl ssh console --command "cd /app && alembic upgrade head"

# Check current revision
flyctl ssh console --command "cd /app && alembic current"

# Rollback (careful!)
flyctl ssh console --command "cd /app && alembic downgrade -1"
```

---

## Monitoring

### Fly.io Logs

```bash
# Live logs
fly logs

# Recent logs
fly logs --tail 100
```

### Health Checks

```bash
# Backend health
curl https://devbuddy-backend.fly.dev/health

# Frontend
curl https://devbuddy.pages.dev
```

### Sentry (Optional)

Set `SENTRY_DSN` secret for automatic error tracking.

---

## Troubleshooting

### Deploy Failed

```bash
# Check Fly.io status
fly status

# Check logs
fly logs

# SSH into VM for debugging
fly ssh console
```

### Database Connection Failed

1. Verify `DATABASE_URL` in Fly.io secrets:
   ```bash
   fly secrets list
   ```

2. Check Supabase connection limits (free tier: 30 concurrent)

3. Verify IP allowlist in Supabase (if enabled)

### CORS Errors

1. Check `VITE_API_BASE_URL` matches Fly.io URL
2. Verify backend CORS allows frontend domain:
   ```python
   # backend/app/main.py
   origins = [
       "https://devbuddy.pages.dev",
       "http://localhost:5173",  # dev
   ]
   ```

### Cold Start Slow

Fly.io free tier sleeps after 5 min idle. First request wakes it (~2s).

To keep warm: Set `min_machines_running = 1` (costs ~$2/mo)

---

## Costs

| Service | Free Tier | Usage |
|---------|-----------|-------|
| Cloudflare Pages | Unlimited bandwidth | Frontend hosting |
| Fly.io | 3 VMs, 3GB volume | 1 backend VM |
| Supabase | 500MB DB, 2GB egress | Database |
| Llama API | 1000 req/day | LLM calls |

**Estimated: $0-3/month** (if staying within free tier)

---

## Rollback

### Backend

```bash
# Rollback to previous deployment
fly deploy --image-ref $(fly releases list | head -2 | tail -1 | awk '{print $2}')
```

### Frontend

Cloudflare Pages keeps last 10 deployments. Rollback via dashboard:
1. Cloudflare Dashboard → Pages → devbuddy
2. Deployments → Select previous → Rollback

### Database

```bash
# Rollback one migration
flyctl ssh console --command "cd /app && alembic downgrade -1"

# Or restore from Supabase backup (if enabled)
```

---

## Custom Domain (Optional)

### Cloudflare Pages

1. Dashboard → Pages → devbuddy → Custom domains
2. Add domain (e.g., `app.yourdomain.com`)
3. Add DNS CNAME record pointing to `devbuddy.pages.dev`

### Fly.io Backend

1. Add certificate:
   ```bash
   fly certs add api.yourdomain.com
   ```

2. Add DNS CNAME `api.yourdomain.com` → `devbuddy-backend.fly.dev`

3. Update `VITE_API_BASE_URL` in wrangler.toml and redeploy

---

**Next**: Read [09_API_REFERENCE.md](./09_API_REFERENCE.md) for API docs.
