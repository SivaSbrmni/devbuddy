# Running DevBuddy on a Mobile Device (Android)

> **Use case:** Demo or personal dev server running on your phone.
> **Not for production** — battery drain, NAT, intermittent connectivity.

## Prerequisites

- Android phone (arm64)
- [Termux](https://f-droid.org/packages/com.termux/) from F-Droid (not Play Store)
- Internet connection

## Quick Start

### 1. Install Termux & core packages

```bash
pkg update && pkg upgrade -y
pkg install python git nodejs-lts openssh
pip install --upgrade pip
```

### 2. Clone DevBuddy

```bash
cd ~
git clone https://github.com/SivaSbrmni/devbuddy.git
cd devbuddy
```

### 3. Backend setup

```bash
cd backend
pip install -r requirements.txt

# Lightweight .env — skip Postgres, use SQLite for mobile demo
cat > .env << 'EOF'
DATABASE_URL=sqlite+aiosqlite:///./devbuddy_mobile.db
SECRET_KEY=mobile-dev-secret-32-chars-long!!
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret-32-chars-minimum!
ENVIRONMENT=development
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
# Point to Ollama Cloud instead of local sidecar
AEP_OLLAMA_BASE_URL=https://ollama.your-cloud.com
OLLAMA_CLOUD_API_KEY=your-key-if-using-cloud
WORKSPACE_ROOT=/data/data/com.termux/files/home/devbuddy-workspaces
REPOS_ROOT=/data/data/com.termux/files/home/devbuddy-repos
AUTO_CREATE_TABLES=1
EOF

# Start the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Frontend setup (optional — skip if API-only)

Open a new Termux session (`swipe left → new session`):

```bash
cd ~/devbuddy/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 5. Expose to the internet

Option A — **Cloudflare Tunnel** (recommended, free):

```bash
pkg install cloudflared
cloudflared tunnel --url http://localhost:8000
# Prints a public URL like https://random-name.trycloudflare.com
```

Option B — **ngrok** (free tier):

```bash
pip install ngrok
ngrok http 8000
```

Option C — **SSH reverse tunnel** (if you have a VPS):

```bash
ssh -R 8080:localhost:8000 user@your-vps.com
```

### 6. Access from anywhere

Use the tunnel URL from step 5. Point the frontend's `VITE_API_BASE_URL`
to the same URL. Share the link with anyone.

---

## LLM Options on Mobile

| Option | Pros | Cons |
|--------|------|------|
| **Ollama Cloud** | Zero local compute, largest models | Requires API key, latency |
| **Meta Llama API** | Free tier available, good models | API key required |
| **Local Ollama in Termux** | Offline-capable | Very slow on mobile CPUs, limited RAM |

For local Ollama (adventurous):
```bash
# Ollama doesn't have an official Termux build, but you can compile from source
# or use a pre-built arm64 binary. This is experimental.
pkg install golang
go install github.com/ollama/ollama@latest
ollama serve &
ollama pull llama3.2:1b  # Use smallest model
```

---

## Keeping It Running

```bash
# Prevent Termux from being killed when the screen is off
termux-wake-lock

# Run in background with tmux
pkg install tmux
tmux new-session -d -s devbuddy 'cd ~/devbuddy/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000'
```

---

## Limitations

- **Battery:** Will drain your phone. Use `termux-wake-lock` + keep charger connected.
- **Performance:** e2-micro GCP VM beats a phone for sustained workloads.
- **Storage:** Phone storage is limited. Use Supabase (cloud Postgres) instead of local DB.
- **Networking:** Mobile carriers use NAT. You need a tunnel (cloudflared/ngrok) for public access.
- **Ollama:** Running large models locally on a phone is impractical. Use cloud LLM endpoints.

## Recommended Architecture for Mobile

```
Phone (Termux)          Cloud
┌──────────────┐    ┌────────────┐
│ FastAPI       │◄──►│ Supabase   │  (Postgres)
│ backend       │    │ (free tier)│
│ :8000         │    └────────────┘
│               │    ┌────────────┐
│               │◄──►│ Ollama     │  (LLM)
│               │    │ Cloud / API│
└──────┬───────┘    └────────────┘
       │
┌──────┴───────┐
│ cloudflared  │
│ tunnel       │──► Public URL
└──────────────┘
```

This gives you a working DevBuddy server on your phone with the heavy
lifting (database + LLM inference) offloaded to free cloud services.
