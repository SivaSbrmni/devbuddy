# 07 — Security Hardening

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [06_AGENT_EXECUTOR.md](./06_AGENT_EXECUTOR.md)

---

## Security Overview

DevBuddy implements defense in depth:

| Layer | Threat | Mitigation |
|-------|--------|------------|
| **Storage** | Token theft | Fernet encryption at rest |
| **Transport** | MITM | HTTPS only, HSTS headers |
| **API** | Abuse | Rate limiting per user/IP |
| **Execution** | Code injection | Sandboxed (e2b/subprocess) |
| **Auth** | Session hijacking | Short-lived JWT, Supabase Auth |
| **Audit** | Repudiation | Immutable signed audit logs |

---

## Token Encryption (Fernet)

**Files**: `backend/app/core/crypto.py`, `api/github_connections.py`, `api/mcp_connections.py`

### How It Works

```python
from cryptography.fernet import Fernet
from app.core.config import settings

# Key derived from SECRET_KEY (deterministic but secure)
# SECRET_KEY must be 32+ chars
_key = base64.urlsafe_b64encode(settings.SECRET_KEY[:32].encode())
_fernet = Fernet(_key)

def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage."""
    if plaintext.startswith("enc::v1::"):
        return plaintext  # Already encrypted
    
    encrypted = _fernet.encrypt(plaintext.encode())
    return f"enc::v1::{encrypted.decode()}"

def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret for use."""
    if not ciphertext.startswith("enc::v1::"):
        return ciphertext  # Plaintext (backward compat)
    
    encrypted = ciphertext[9:]  # Remove prefix
    return _fernet.decrypt(encrypted.encode()).decode()
```

### Usage in API

```python
# backend/app/api/github_connections.py

@router.post("/github-connections")
async def create_connection(
    repo_url: str,
    github_token: str,
    db: AsyncSession = Depends(get_db)
):
    # Encrypt before storage
    encrypted_token = encrypt_secret(github_token)
    
    conn = GithubConnection(
        repo_url=repo_url,
        github_token=encrypted_token
    )
    db.add(conn)
    await db.commit()
    
    # Return without token (never expose in API response)
    return {"id": conn.id, "repo_url": repo_url}

# When using for git operations
async def clone_repo(connection_id: UUID):
    conn = await get_connection(connection_id)
    
    # Decrypt only when needed
    token = decrypt_secret(conn.github_token)
    
    # Use token for git clone
    git.clone(url=conn.repo_url, token=token)
```

### Fields Encrypted

| Table | Field | Encrypted? |
|-------|-------|------------|
| `github_connections` | `github_token` | ✅ Yes |
| `mcp_connections` | `api_key` | ✅ Yes |

---

## Rate Limiting (slowapi)

**File**: `backend/app/core/ratelimit.py`

### Configuration

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Memory-backed storage (use Redis in production)
limiter = Limiter(
    key_func=get_remote_address,  # Default: per IP
    enabled=True
)

# Rate limit constants
RATE_GLOBAL = "60/minute"          # Per IP, all endpoints
RATE_CHAT = "30/hour"              # Per user, chat messages
RATE_TASK = "6/hour"               # Per user, task creation
```

### Usage

```python
# backend/app/api/chat.py
from app.core.ratelimit import limiter, RATE_CHAT

@router.post("/chat")
@limiter.limit(RATE_CHAT)
async def chat_endpoint(request: Request, ...):
    # Max 30 chat messages per hour per user
    pass

# backend/app/api/tasks.py
@router.post("/tasks")
@limiter.limit(RATE_TASK)
async def create_task(request: Request, ...):
    # Max 6 tasks per hour per user
    pass
```

### Per-User Rate Limiting

Uses `request.state.user` set by auth middleware:

```python
# In auth middleware
def get_user_from_jwt(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = verify_supabase_jwt(token)
    request.state.user = user
    return user

# Rate limit uses user ID if available, falls back to IP
@limiter.limit(RATE_CHAT)
async def chat(request: Request):
    user_id = getattr(request.state, "user", {}).get("id")
    key = user_id or get_remote_address(request)
    # ... slowapi handles key automatically
```

---

## Sandboxed Code Execution

**File**: `backend/app/services/skills.py`

### Configuration

```python
SANDBOX_BACKEND = os.getenv("SANDBOX_BACKEND", "disabled")
# Options: "e2b" | "subprocess" | "disabled"
```

### Security Tiers

| Tier | Isolation | Use Case |
|------|-----------|----------|
| **disabled** | No execution | Default, production-safe |
| **subprocess** | Process-level | Local development only |
| **e2b** | MicroVM (firecracker) | Production with e2b key |

### Implementation

```python
async def run_python(code: str) -> str:
    """Execute Python code in configured sandbox."""
    
    backend = os.getenv("SANDBOX_BACKEND", "disabled")
    
    if backend == "disabled":
        return "Error: Sandbox disabled for security. Set SANDBOX_BACKEND=e2b or subprocess to enable."
    
    elif backend == "e2b":
        return await _run_e2b(code)
    
    elif backend == "subprocess":
        return await _run_subprocess(code)
    
    else:
        return f"Error: Unknown sandbox backend: {backend}"

async def _run_e2b(code: str) -> str:
    """Run in e2b.dev microVM."""
    from e2b import Sandbox
    
    sbx = Sandbox(api_key=os.getenv("E2B_API_KEY"))
    
    # Timeout 30s, network disabled
    result = sbx.run_code(
        code,
        timeout=30,
        env_vars={},
        on_network=False
    )
    
    return result.stdout + result.stderr

async def _run_subprocess(code: str) -> str:
    """Run in local subprocess (dev only)."""
    import tempfile
    import subprocess
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = subprocess.run(
            ['python', f.name],
            capture_output=True,
            text=True,
            timeout=30,
            # Restrictions:
            # - No network (firewall)
            # - Limited filesystem access
        )
        
        return result.stdout + result.stderr
```

### Security Recommendations

**Production**:
- Use `SANDBOX_BACKEND=e2b` with valid API key
- Never use `subprocess` in production

**Development**:
- Use `SANDBOX_BACKEND=subprocess` for local testing
- Or use `ollama` LLM which runs locally anyway

---

## Authentication & Authorization

**File**: `backend/app/core/security.py`

### JWT Verification

```python
import jwt
from app.core.config import settings

SUPABASE_JWT_SECRET = settings.SUPABASE_JWT_SECRET

async def verify_token(token: str) -> dict:
    """Verify Supabase JWT and return user payload."""
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return {
            "id": payload["sub"],
            "email": payload["email"],
            "tenant_id": payload.get("tenant_id", "default")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

### Protected Routes

```python
from fastapi import Depends, HTTPException
from app.core.security import verify_token

async def get_current_user(token: str = Header(..., alias="Authorization")):
    if not token.startswith("Bearer "):
        raise HTTPException(401, "Invalid auth header")
    
    token = token[7:]  # Remove "Bearer "
    return await verify_token(token)

@router.get("/tasks")
async def list_tasks(user: dict = Depends(get_current_user)):
    # Only returns tasks for this user/tenant
    return await get_tasks_for_user(user["id"])
```

### Tenant Isolation

All queries include `tenant_id` filter:

```python
async def get_task(task_id: UUID, tenant_id: str):
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.tenant_id == tenant_id  # Enforce isolation
        )
    )
    return result.scalar_one_or_none()
```

---

## Audit Logging

**File**: `backend/app/models/audit_log.py`

### Immutable Logs

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    
    # What happened
    event_type = Column(String, nullable=False)  # 'task_created', 'llm_call', etc.
    actor = Column(String, nullable=False)     # 'user', 'system', 'agent'
    
    # Context
    task_id = Column(UUID, ForeignKey("tasks.id"))
    details_json = Column(JSONB)  # Arbitrary event data
    
    # Tamper-evident
    created_at = Column(DateTime, default=datetime.utcnow)
    # Note: No updated_at — logs are immutable
```

### Usage

```python
async def log_audit(
    tenant_id: str,
    event_type: str,
    actor: str,
    task_id: UUID = None,
    details: dict = None
):
    log = AuditLog(
        tenant_id=tenant_id,
        event_type=event_type,
        actor=actor,
        task_id=task_id,
        details_json=details or {}
    )
    db.add(log)
    await db.commit()

# In agent executor
await log_audit(
    tenant_id=tenant_id,
    event_type="subtask_completed",
    actor="agent",
    task_id=task_id,
    details={"subtask_id": subtask.id, "skill": "write_file"}
)
```

---

## Environment Security

### Required Secrets

| Variable | Purpose | Source |
|----------|---------|--------|
| `SECRET_KEY` | Fernet encryption | `openssl rand -hex 32` |
| `SUPABASE_JWT_SECRET` | JWT verification | Supabase dashboard |
| `DATABASE_URL` | DB connection | Supabase connection string |
| `LLM_API_KEY` | LLM access | Provider dashboard |

### Secrets Management

**Development**: `.env` file (gitignored)
**Production**: Fly.io secrets

```bash
# Set Fly.io secrets
fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
fly secrets set SUPABASE_JWT_SECRET="..."
fly secrets set DATABASE_URL="..."
fly secrets set LLM_API_KEY="..."
```

### Never Commit

```gitignore
# .gitignore
.env
.env.local
.env.production
*.pem
*.key
```

---

## Security Checklist

Before deploying:

- [ ] `SECRET_KEY` is 32+ random characters
- [ ] `SANDBOX_BACKEND` is `e2b` or `disabled` (never `subprocess` in prod)
- [ ] Rate limiting enabled
- [ ] All tokens encrypted at rest
- [ ] Database uses Supabase (not exposed)
- [ ] HTTPS enforced
- [ ] CORS restricted to known origins
- [ ] Sentry configured for error tracking
- [ ] Audit logging active

---

**Next**: Read [08_DEPLOYMENT.md](./08_DEPLOYMENT.md) for deployment.
