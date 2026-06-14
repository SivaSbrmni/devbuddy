# 08 — Deployment Guide

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [07_SECURITY_HARDENING.md](./07_SECURITY_HARDENING.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GITHUB PAGES                                │
│                  (Frontend - Free)                               │
│                   devbuddy.org                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS / Cross-Origin
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  HUGGINGFACE SPACES                              │
│                  (Backend - Free Tier)                           │
│           sivasbrmni-devbuddy.hf.space                          │
│                                                                  │
│  • Auto-sleep after idle period                                  │
│  • Auto-wake on request (cold start ~10-30s)                    │
│  • Docker-based deployment                                       │
│  • Embedded PostgreSQL for persistence                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Automated Deployment

Deployment is fully automated via `.github/workflows/deploy.yml`.
Every push to `main` triggers:

1. **Frontend** → Builds React app, deploys to GitHub Pages
2. **Backend** → Pushes backend code to HuggingFace Spaces repo
3. **Smoke Tests** → Verifies both endpoints respond

### Required GitHub Secret

| Secret     | Source                                          |
|------------|-------------------------------------------------|
| `HF_TOKEN` | https://huggingface.co/settings/tokens (Write) |

### Setup (one-time)

1. **GitHub Pages**: Go to repo Settings → Pages → Source: **GitHub Actions**
2. **Custom domain**: In Pages settings, set custom domain to `devbuddy.org`
3. **DNS**: A records pointing to GitHub Pages IPs (see below)
4. **HF Token**: Add `HF_TOKEN` to repo Settings → Secrets → Actions

---

## DNS Configuration (devbuddy.org)

### A Records (apex domain)

| Type | Host | Value             |
|------|------|-------------------|
| A    | `@`  | `185.199.108.153` |
| A    | `@`  | `185.199.109.153` |
| A    | `@`  | `185.199.110.153` |
| A    | `@`  | `185.199.111.153` |

### CNAME (www subdomain)

| Type  | Host  | Value                    |
|-------|-------|--------------------------|
| CNAME | `www` | `sivasbrmni.github.io`  |

---

## Manual Deployment

### Frontend (if workflow fails)

```bash
cd frontend
npm ci
VITE_API_URL=https://sivasbrmni-devbuddy.hf.space \
VITE_API_BASE_URL=https://sivasbrmni-devbuddy.hf.space \
  npm run build

# Deploy via gh-pages or push dist/ contents to gh-pages branch
```

### Backend (if workflow fails)

```bash
# Clone your HF Space
git clone https://huggingface.co/spaces/sivasbrmni/devbuddy hf-space
cd hf-space

# Replace contents with backend/
rm -rf *
cp -r /path/to/devbuddy/backend/* .

# Push
git add -A
git commit -m "manual deploy"
git push
```

---

## Environment Variables (HuggingFace Space)

Set these in the HF Space settings (Settings → Repository secrets):

| Variable               | Required | Description                          |
|------------------------|----------|--------------------------------------|
| `DATABASE_URL`         | Yes      | PostgreSQL connection string         |
| `SECRET_KEY`           | Yes      | JWT signing key (32+ chars)          |
| `LLM_PROVIDER`         | Yes      | `ollama` or `llama`                  |
| `LLM_MODEL`            | Yes      | e.g., `llama3.2:latest`              |
| `LLM_API_KEY`          | No       | Required if using Llama/Groq API     |
| `SUPABASE_URL`         | No       | For Supabase auth integration        |
| `SUPABASE_ANON_KEY`    | No       | Public anon key                      |
| `SUPABASE_JWT_SECRET`  | No       | For JWT verification                 |
| `SENTRY_DSN`           | No       | Error tracking                       |

### AEP-specific (Phase 2+)

| Variable                      | Required | Description                     |
|-------------------------------|----------|---------------------------------|
| `AEP_OLLAMA_BASE_URL`        | No       | Ollama instance URL             |
| `OLLAMA_CLOUD_API_KEY`       | No       | Ollama Cloud auth               |
| `AEP_SECRET_ENCRYPTION_KEY`  | No       | AES-256 key for secret manager  |
| `GITHUB_APP_ID`              | No       | GitHub App integration          |
| `GITHUB_APP_PRIVATE_KEY`     | No       | GitHub App private key (PEM)    |
| `GITHUB_APP_INSTALLATION_ID` | No       | GitHub App installation ID      |
| `GITHUB_WEBHOOK_SECRET`      | No       | HMAC verification secret        |

> **Note:** AEP features remain dormant (all feature flags default OFF)
> until explicitly enabled via the admin API. The base DevBuddy
> functionality works without any AEP variables configured.

---

## CORS Configuration

The backend allows requests from:

- `https://devbuddy.org`
- `https://www.devbuddy.org`
- `https://sivasbrmni-devbuddy.hf.space`
- `http://localhost:5173` (local dev)

---

## Verification

```bash
# Check frontend
curl -I https://devbuddy.org
# Expected: HTTP/2 200

# Check backend health
curl https://sivasbrmni-devbuddy.hf.space/health
# Expected: {"status":"healthy","service":"devbuddy-lite"}

# Check DNS
dig +short devbuddy.org A
# Expected: 185.199.108.153, 185.199.109.153, ...
```

---

## Troubleshooting

| Issue                     | Solution                                               |
|---------------------------|--------------------------------------------------------|
| Frontend 404              | Ensure Pages source is "GitHub Actions" not "branch"   |
| Backend 503               | HF Space sleeping — visit URL to wake it               |
| CORS errors               | Verify backend CORS config includes `devbuddy.org`     |
| Deploy workflow fails     | Check `HF_TOKEN` secret is valid and has Write access  |
| DNS not resolving         | Wait for propagation (up to 48h); verify A records     |
| HTTPS unavailable         | DNS must resolve before GitHub provisions SSL cert      |
| Build fails (TypeScript)  | Check `frontend/tsconfig.json` for strict mode issues  |

---

## See also

- `.github/workflows/deploy.yml` — CI/CD pipeline
- `backend/Dockerfile` — Container configuration
- `docs/aep-github-app-setup.md` — GitHub App integration guide
