# DevBuddy Sanity Check Document

> Generated: 2026-06-15  
> Target URL: `https://sivasbrmni-devbuddy.hf.space`  
> Method: Playwright MCP (UI + API validation)

---

## 1. Summary

| Category | Status | Details |
|----------|--------|---------|
| **Space Status** | ✅ RUNNING | Stage: `RUNNING`, no runtime errors |
| **Health Check** | ✅ PASS | `/health` → `200 {status: healthy}` |
| **DB Health** | ✅ PASS | `/health/db` → `200 {database: connected}` |
| **Models API** | ✅ PASS | `/api/v1/models` → 4 models (Llama + 3 Ollama) |
| **Landing Page** | ✅ PASS | Renders correctly, no console errors |
| **Auth Flow** | ✅ PASS | Google OAuth redirect URL correct |
| **Responsive** | ✅ PASS | Mobile (390×844) & Desktop (1440×900) render correctly |
| **Error Handling** | ✅ PASS | 404s return JSON, invalid routes fallback to landing |
| **Static Assets** | ✅ PASS | No failed CSS/JS/image requests |

**Overall Result: 18/18 automated tests PASS (Playwright)**

---

## 2. Test Results (Playwright MCP)

### 2.1 Landing Page

| Test | Result |
|------|--------|
| Page title = "DevBuddy Lite" | ✅ |
| Hero text visible | ✅ |
| 4 feature cards visible (Agents, Routing, Tools, Deploy) | ✅ |
| "Continue with Google" button visible & enabled | ✅ |
| Footer "© 2026 DevBuddy" visible | ✅ |
| Zero console errors on load | ✅ |

**Screenshot:** `test-01-landing-page.png`

### 2.2 Responsive Layout

| Viewport | Result |
|----------|--------|
| Desktop (1440×900) | ✅ Full layout renders |
| Mobile (390×844) | ✅ No horizontal scroll |

**Screenshot:** `test-02-mobile-view.png`

### 2.3 Auth Flow

| Test | Result |
|------|--------|
| Click "Continue with Google" | ✅ Opens Google OAuth popup |
| OAuth redirect URL contains correct `redirect_uri` | ✅ `https://sivasbrmni-devbuddy.hf.space/api/v1/auth/google/callback` |

### 2.4 API Health

```json
GET /health
{
  "status": "healthy",
  "service": "devbuddy-lite"
}
```

```json
GET /health/db
{
  "status": "healthy",
  "database": "connected"
}
```

### 2.5 Models API

```json
GET /api/v1/models
[
  {"id": "llama-4-scout-17b-16e-instruct", "label": "Llama 4 Scout",   "provider": "llama",  "family": "llama"},
  {"id": "qwen3-coder:480b",               "label": "Qwen 3 Coder",     "provider": "ollama", "family": "ollama"},
  {"id": "llama3.3:latest",                "label": "Llama 3.3",        "provider": "ollama", "family": "ollama"},
  {"id": "deepseek-coder:latest",          "label": "DeepSeek Coder",   "provider": "ollama", "family": "ollama"}
]
```

| Model | Provider | Status |
|-------|----------|--------|
| Llama 4 Scout | llama | ✅ |
| Qwen 3 Coder | ollama | ✅ |
| Llama 3.3 | ollama | ✅ |
| DeepSeek Coder | ollama | ✅ |

### 2.6 Error Handling

| Test | Expected | Actual |
|------|----------|--------|
| `GET /api/v1/nonexistent` | 404 JSON | ✅ `{"detail":"Not found"}` |
| `GET /api/v1/settings` (no token) | 422 validation error | ✅ `{"detail":[{"type":"missing",...}]}` |
| `GET /app/nonexistent` | Redirect to `/` | ✅ Falls back to landing page |

### 2.7 Performance Smoke

| Test | Result |
|------|--------|
| Landing page load time | ✅ < 5 seconds |
| All static assets (CSS/JS/images) | ✅ All return 200 |

---

## 3. Automated Test Suite

A reusable Playwright test spec is created at:

```
frontend/e2e/sanity.spec.ts
frontend/playwright.config.ts
```

### Run the suite locally

```bash
cd frontend
npm install -D @playwright/test
npx playwright install chromium

# Test against deployed space (default)
npx playwright test e2e/sanity.spec.ts

# Test against custom URL
DEVBUDDY_URL=https://your-url.hf.space npx playwright test e2e/sanity.spec.ts
```

**Latest run:** `18 passed (41.5s)` — Chromium headless, 2026-06-15

### Test categories covered

1. **Landing Page** — title, hero, features, sign-in button, footer, console errors
2. **Responsive Layout** — mobile & desktop viewports, no layout breakage
3. **Auth Flow** — Google OAuth redirect URL validation
4. **API Health** — `/health`, `/health/db`
5. **Models API** — model list presence, required fields, Ollama population
6. **Error Handling** — 404s, auth failures, route fallbacks
7. **Performance** — load time < 5s, all assets 200

---

## 4. Known Issues / Notes

- **Database init**: The previous `DuplicateTableError` on HF Space restarts has been fixed by wrapping `Base.metadata.create_all()` in a `try/except` that ignores `"already exists"` and `"duplicate"` errors.
- **Docker cache-busting**: Added `RUN rm -rf` + cache-bust echo to force fresh code copies on rebuild.
- **Runtime safety**: `deploy/start.sh` drops the conflicting index at startup as a secondary guard.

---

## 5. Checklist for Future Deploys

- [ ] `git push hf main:main --force` succeeded
- [ ] Factory reboot triggered via `HfApi.restart_space(..., factory_reboot=True)`
- [ ] Stage transitions: `BUILDING` → `RUNNING` (not `RUNTIME_ERROR`)
- [ ] `GET /health` returns 200
- [ ] `GET /health/db` returns 200
- [ ] `GET /api/v1/models` returns non-empty array with Ollama models
- [ ] Landing page renders with zero console errors
- [ ] Google sign-in button opens OAuth popup with correct redirect URI
- [ ] No 4xx/5xx on static assets (CSS, JS, images)

---

*Document generated by Playwright MCP automated testing.*
