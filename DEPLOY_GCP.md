# GCP Deployment Guide — DevBuddy (Free Tier)

## Architecture: Single e2-micro VM + Persistent Disk

Everything runs on one free-tier VM. All data persists on a 30GB attached disk.

```
e2-micro VM (us-central1 — always free)
  └── /mnt/data/              ← 30GB persistent disk
       ├── postgres_data/     ← DB never lost on restart
       ├── loki_data/
       ├── grafana_data/
       ├── workspaces/        ← generated code artifacts
       └── repos/             ← cloned GitHub repos
```

---

## Step 1 — Create the VM

Run these in Google Cloud Shell (cloud.google.com → activate Cloud Shell):

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export ZONE=us-central1-a
export VM_NAME=devbuddy-vm

# Create the VM (e2-micro is always free in us-central1)
gcloud compute instances create $VM_NAME \
  --zone=$ZONE \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata=enable-oslogin=true

# Allow HTTP/HTTPS traffic
gcloud compute firewall-rules create allow-http \
  --allow=tcp:80,tcp:443 \
  --target-tags=http-server,https-server \
  --direction=INGRESS

# Get the external IP
gcloud compute instances describe $VM_NAME --zone=$ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

**Note that IP** — point your domain DNS A record to it.

---

## Step 2 — SSH into the VM and install Docker

```bash
gcloud compute ssh $VM_NAME --zone=$ZONE
```

Inside the VM:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt-get install -y docker-compose-plugin git

# Verify
docker --version
docker compose version
```

---

## Step 3 — Create persistent data directory

The boot disk is 30GB and persists across reboots. Use it directly:

```bash
sudo mkdir -p /opt/devbuddy/data/{postgres,loki,grafana,workspaces,repos}
sudo chown -R $USER:$USER /opt/devbuddy
```

---

## Step 4 — Clone the repo and configure

```bash
cd /opt/devbuddy
git clone https://github.com/SivaSbrmni/devbuddy.git .
```

Create `.env.prod` file (this stays on the VM — never commit this):

```bash
cat > /opt/devbuddy/.env.prod << 'EOF'
# PostgreSQL
POSTGRES_USER=devbuddy
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD_HERE
POSTGRES_DB=devbuddy

# App
SECRET_KEY=CHANGE_ME_RUN_openssl_rand_hex_32
ENVIRONMENT=production
LOG_LEVEL=INFO

# Supabase (get from supabase.com → project settings → API)
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_JWT_SECRET=YOUR_JWT_SECRET

# LLM (get from console.groq.com — free tier)
LLM_PROVIDER=groq
LLM_MODEL=llama3-8b-8192
LLM_API_KEY=gsk_YOUR_GROQ_KEY

# Frontend
VITE_API_BASE_URL=http://YOUR_VM_IP:8000

# Grafana
GRAFANA_PASSWORD=CHANGE_ME_GRAFANA_PASSWORD

# Workspaces (persistent paths)
WORKSPACE_ROOT=/opt/devbuddy/data/workspaces
REPOS_ROOT=/opt/devbuddy/data/repos
EOF
```

Generate a strong SECRET_KEY:
```bash
openssl rand -hex 32
# paste the result into SECRET_KEY above
```

---

## Step 5 — Update docker-compose.prod.yml to use persistent paths

The volumes in docker-compose.prod.yml need to point to `/opt/devbuddy/data/`:

```bash
# Already updated by the deploy script below — just run it
```

---

## Step 6 — Deploy

```bash
cd /opt/devbuddy

# Build images locally (since we're not using GHCR on free tier)
docker compose -f docker-compose.prod.yml build

# Start everything
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f backend
```

---

## Step 7 — Verify data persistence

```bash
# Check postgres data directory is populated
ls /opt/devbuddy/data/postgres/
# Should show: base/ global/ pg_wal/ etc.

# Restart the VM to confirm data survives
sudo reboot

# After reboot, SSH back in and check
cd /opt/devbuddy
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

---

## GitHub Actions Secrets (for CI/CD)

Go to: https://github.com/SivaSbrmni/devbuddy/settings/secrets/actions

| Secret | Value | Where to get |
|--------|-------|--------------|
| `DEPLOY_HOST` | VM external IP | Step 1 output |
| `DEPLOY_USER` | `your-google-account_gmail_com` | `whoami` on VM |
| `DEPLOY_SSH_KEY` | Contents of `~/.ssh/id_rsa` | See Step 8 |
| `VITE_API_BASE_URL` | `http://YOUR_VM_IP:8000` | VM IP from Step 1 |
| `VITE_SUPABASE_URL` | `https://xxx.supabase.co` | Supabase dashboard |
| `VITE_SUPABASE_ANON_KEY` | `eyJ...` | Supabase dashboard |

---

## Step 8 — Set up SSH key for GitHub Actions deployment

On the VM:
```bash
# Generate deploy key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key -N ""

# Add public key to authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# Print private key — copy this entire output into DEPLOY_SSH_KEY secret
cat ~/.ssh/deploy_key
```

Copy the **private key** (everything from `-----BEGIN OPENSSH PRIVATE KEY-----` to `-----END OPENSSH PRIVATE KEY-----`) into the `DEPLOY_SSH_KEY` GitHub secret.

---

## Where Each Key Comes From

| Key | Service | URL |
|-----|---------|-----|
| `SUPABASE_URL` | Supabase (auth) | supabase.com → project → Settings → API |
| `SUPABASE_ANON_KEY` | Supabase | Same page → `anon public` key |
| `SUPABASE_JWT_SECRET` | Supabase | Settings → API → JWT Secret |
| `LLM_API_KEY` | Groq (free LLM) | console.groq.com → API Keys |
| `SECRET_KEY` | Generated | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | You choose | Use a strong random password |

---

## Cost Summary

| Resource | Cost |
|---------|------|
| e2-micro VM (us-central1) | **Free** (always free tier) |
| 30GB boot disk | **Free** (always free tier) |
| External IP (attached) | **Free** while VM running |
| Network egress < 1GB | **Free** |
| **Total** | **$0/month** |

> Note: e2-micro has 1 vCPU + 1GB RAM. It will be slow for large LLM tasks but fine for testing. Upgrade to e2-small (~$13/month) for production use.

---

## Auto-start on VM reboot

```bash
# Create systemd service so docker compose starts automatically
sudo tee /etc/systemd/system/devbuddy.service > /dev/null << 'EOF'
[Unit]
Description=DevBuddy Platform
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/devbuddy
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable devbuddy
sudo systemctl start devbuddy
```

Now if the VM reboots (GCP maintenance, etc.), DevBuddy auto-starts with all data intact.
