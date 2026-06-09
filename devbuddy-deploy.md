# DevBuddy Deployment Guide — devbuddy.org

## Architecture

| Component | Platform | URL |
|-----------|----------|-----|
| **Frontend** (React/Vite) | GitHub Pages | `https://devbuddy.org` |
| **Backend** (FastAPI) | HuggingFace Spaces | `https://sivasbrmni-devbuddy.hf.space` |
| **Database** | PostgreSQL (embedded in HF Space) | Internal |

Frontend makes cross-origin API calls to the HF Spaces backend. CORS is pre-configured.

---

## Step 1: Enable GitHub Pages (already done if reading this)

1. Go to: **https://github.com/SivaSbrmni/devbuddy/settings/pages**
2. Under **"Build and deployment"** → Source: select **"Deploy from a branch"**
3. Branch: select **`gh-pages`** / **`/ (root)`**
4. Click **Save**
5. Under **"Custom domain"**: type **`devbuddy.org`** → click **Save**
6. Check **"Enforce HTTPS"** (available after DNS propagation)

---

## Step 2: Update DNS Records (Google Domains / Squarespace)

Go to your domain registrar's DNS settings for `devbuddy.org`.

### Remove old A records (Squarespace defaults)

```
198.185.159.144
198.185.159.145
198.49.23.145
198.49.23.144
```

### Add GitHub Pages A records

| Type | Host | Value |
|------|------|-------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |

### Add CNAME record for www

| Type | Host | Value |
|------|------|-------|
| CNAME | `www` | `sivasbrmni.github.io` |

### DNS Propagation

- Typically takes **5–30 minutes**
- Can take up to **48 hours** in rare cases
- Verify with: `dig devbuddy.org A` — should return the GitHub Pages IPs above

---

## Step 3: Verify Deployment

After DNS propagation:

```bash
# Check DNS resolves to GitHub Pages
dig +short devbuddy.org A
# Expected: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153

# Check site is live
curl -I https://devbuddy.org
# Expected: HTTP/2 200

# Check backend is reachable (CORS)
curl -I https://sivasbrmni-devbuddy.hf.space/health
# Expected: {"status":"healthy","service":"devbuddy-lite"}
```

---

## Step 4: Enforce HTTPS

Once DNS check passes in GitHub Pages settings:

1. Go to **https://github.com/SivaSbrmni/devbuddy/settings/pages**
2. Check **"Enforce HTTPS"**

GitHub provisions a free SSL certificate via Let's Encrypt automatically.

---

## Auto-Deployment

A GitHub Actions workflow (`.github/workflows/deploy-pages.yml`) automatically rebuilds and deploys the frontend whenever changes are pushed to `main` that modify `frontend/` files.

The workflow:
1. Builds the React app with `VITE_API_URL=https://sivasbrmni-devbuddy.hf.space`
2. Generates the `CNAME` file for `devbuddy.org`
3. Creates a `404.html` for SPA routing
4. Deploys to GitHub Pages

---

## Backend Updates

The backend runs on HuggingFace Spaces at `https://sivasbrmni-devbuddy.hf.space`.

To update:
- Push backend changes to the HuggingFace repo (via HF Hub API or git)
- The Space auto-rebuilds on push

CORS is configured to allow requests from:
- `https://devbuddy.org`
- `https://www.devbuddy.org`
- `https://sivasbrmni-devbuddy.hf.space`
- `http://localhost:5173` (local dev)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| DNS check unsuccessful | Wait for propagation; verify A records with `dig devbuddy.org A` |
| 404 on devbuddy.org | Ensure `gh-pages` branch exists and has `index.html` + `CNAME` |
| CORS errors in browser | Check backend CORS config includes `https://devbuddy.org` |
| Backend 503 | HF Space may be sleeping; visit `https://sivasbrmni-devbuddy.hf.space` to wake it |
| HTTPS unavailable | DNS must fully propagate before GitHub can provision SSL cert |
