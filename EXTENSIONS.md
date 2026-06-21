# DevBuddy Autonomous Engineering Platform — Extension Documentation

> **Spec:** `autonomous-ai-platform-spec.md` — Free-Tier Multi-LLM Edition
> **Status:** Phases 0-4, 6 implemented. LLM Gateway now uses the existing user-level provider configuration (`user_llm_providers`) with no hardcoded API keys. Phase 5 (frontend) and end-to-end test pending.

---

## Overview

The Autonomous Engineering Platform (AEP) extends DevBuddy with a multi-provider LLM gateway, lossless compression pipeline, GitHub Actions execution engine, agent plugin system, memory/context engine, and security hardening — all behind feature flags for incremental rollout.

---

## Feature Flags

All AEP features are gated behind runtime-evaluable feature flags. Flags default to **off**, ensuring backward compatibility.

**File:** `backend/app/core/feature_flags.py`

| Flag | Default | Purpose |
|------|---------|---------|
| `autonomous_engine_enabled` | false | Master kill switch |
| `llm_gateway_enabled` | false | Enable /LLM routes |
| `github_actions_runtime_enabled` | false | Enable GHA execution |
| `agent_planner_enabled` | false | Enable planner agent |
| `agent_coder_enabled` | false | Enable coder agent |
| `agent_debugger_enabled` | false | Enable debugger agent |
| `memory_system_enabled` | false | Enable context engine |
| `multi_agent_enabled` | false | Enable multi-agent coordination |
| `autonomous_ui_enabled` | false | Enable frontend modules |
| `webhook_receiver_enabled` | false | Enable GitHub webhooks |
| `compression_pipeline_enabled` | **true** | Compression (no functional downside) |

**Enabling flags:**
```bash
# Global (environment variable)
export AEP_FLAG_LLM_GATEWAY_ENABLED=true

# Per-tenant (via API or code)
feature_flags.set_tenant_override("tenant-123", "llm_gateway_enabled", True)
```

**Usage in code:**
```python
from app.core.feature_flags import feature_flags

if feature_flags.is_enabled("llm_gateway_enabled"):
    # ... feature-gated code
```

---

## Compatibility Adapter Layer (Seam 1)

**File:** `backend/app/core/compat_adapter.py`

Bridges the existing DevBuddy app with the AEP extension. Provides:
- `on_task_created()` / `on_task_completed()` — event hooks
- `get_auth_context()` — extracts auth from JWT payload
- `get_repository_record()` — converts existing repo format to AEP model
- `emit_notification()` — sends events to the existing app's notification system

All methods are safe no-ops when `autonomous_engine_enabled` is false.

---

## LLM Gateway (Seam 3 + 4)

**Files:**
- `backend/app/llm/gateway.py` — Main gateway singleton
- `backend/app/llm/providers/` — Provider implementations
- `backend/app/llm/quota.py` — Quota ledger + circuit breaker
- `backend/app/api/routes/llm_gateway.py` — HTTP routes

### API Routes (all under `/api/v1/LLM`)

| Route | Method | Description |
|-------|--------|-------------|
| `/LLM/chat` | POST | Non-streaming chat completion |
| `/LLM/generate` | POST | Text generation |
| `/LLM/stream` | POST | Streaming chat (SSE) |
| `/LLM/embeddings` | POST | Text embeddings |
| `/LLM/context` | POST | Context-aware completion with compression |
| `/LLM/tools` | POST | Tool-calling completion |
| `/LLM/route` | POST | Preview provider cascade for a task type |
| `/LLM/models` | GET | List available models from all providers |
| `/LLM/health` | GET | Gateway health + provider status |

### Provider Source: User Configuration (No Hardcoded Keys)

The LLM Gateway does **not** read API keys from environment variables or hardcoded secrets. Instead, it loads the current user's providers from the existing **`user_llm_providers`** table, decrypts the stored API keys with the existing Fernet crypto, and routes through them.

**File:** `backend/app/llm/providers/user_provider.py`

Supported `provider_type` values from the universal provider config:

| `provider_type` | API Style | Endpoint examples |
|-----------------|-----------|-------------------|
| `openai-compatible` | OpenAI `/chat/completions` + `/embeddings` | OpenRouter, Groq, Cerebras, Mistral, Azure, custom endpoints |
| `anthropic` | Anthropic `/v1/messages` | Claude API |
| `ollama` | Ollama `/api/chat` + `/api/tags` | Local/cloud Ollama |
| `google` | OpenAI-compatible endpoint (configure base URL) | Gemini OpenAI-compatible endpoints |

### Task → Provider Cascade

The cascade is built per user, per request:

1. **Routing rules** (`provider_routing_rules` table): task-specific priority chains (e.g., `coding` → Provider A, `planning` → Provider B)
2. **User provider priority** (`priority` column on `user_llm_providers`): global fallback order when no routing rule matches
3. **AEP task type mapping** maps `planner/coder/debugger/reviewer/test/security/docs/devops/docs_summary/embeddings` to the existing routing task types

### Routing Algorithm

1. Compress payload (compression pipeline)
2. Get user-specific cascade for task type
3. For each provider in cascade:
   - Skip if quota would exceed
   - Skip if circuit breaker is cooling down
   - Try call → on success: record quota, return normalized response
   - On 429/5xx: cool down provider, continue to next
4. All exhausted → enqueue to `aep_pending_queue`

### Configuration

1. Use the existing frontend **Settings → My Providers** page (or `POST /api/v1/llm-providers`)
2. Add one or more providers with their encrypted API key, base URL, default model, and priority
3. Optionally add routing rules via `POST /api/v1/llm-providers/{id}/rules`
4. Enable the gateway: `AEP_FLAG_LLM_GATEWAY_ENABLED=true`

No API keys are stored in code, environment variables, or deployment configs.

---

## Compression Pipeline (Part 3)

**File:** `backend/app/llm/compression.py`

Applied to every outbound LLM request, in order:
1. **TOON structural encoding** — lossless re-encoding of tabular JSON
2. **Reference deduplication** — repeated blocks replaced with `<ref:id>`
3. **Diff-based file context** — deltas only after first send
4. **Semantic chunk retrieval** — scoping (not alteration)
5. **Whitespace normalization** — skips whitespace-sensitive formats

**Lossless invariant:** `decode(encode(x)) === x` for every compressor.

**Tests:** `backend/tests/test_compression.py` — 82 tests, all passing.

---

## Database Schema (Part 4)

**File:** `backend/app/models/aep.py`

All tables use `aep_` prefix (additive, no conflicts with existing tables):

| Table | Purpose |
|-------|---------|
| `aep_tasks` | Autonomous engineering tasks |
| `aep_repositories` | Registered GitHub repos |
| `aep_executions` | Agent execution records |
| `aep_memory` | Long-term memory with pgvector embeddings |
| `aep_workflows` | Generated GHA workflow YAML |
| `aep_pending_queue` | Queue for exhausted-cascade retries |
| `aep_audit_log` | Security audit trail |

---

## GitHub Actions Execution Engine (Part 5)

**File:** `backend/app/execution/gha_runtime.py`

Lifecycle: Planner builds DAG → Workflow YAML generated → `workflow_dispatch` triggers ephemeral runner → checkout → context hydration → agent steps → artifacts uploaded → results posted back → runner terminates.

No persistent runner state; all persistence is external.

---

## Plugin Registry + Agent Interface (Part 1)

**File:** `backend/app/agents/plugin_registry.py`

All agents implement the `AgentPlugin` interface:
```python
class AgentPlugin(ABC):
    name: str
    version: str
    capabilities: list[str]
    async def initialize(ctx: PlatformContext) -> None
    def can_handle(task: Task) -> bool
    async def execute(task: Task, ctx: ExecutionContext) -> AgentResult
    async def on_success(result: AgentResult) -> None
    async def on_failure(error: AgentError) -> None
    async def shutdown() -> None
```

**Capabilities:** planning, coding, debugging, reviewing, testing, security, docs, devops, coordination.

---

## Memory & Context Engine (Part 7)

**File:** `backend/app/memory/context_engine.py`

| Type | Storage | TTL | Purpose |
|------|---------|-----|---------|
| Working context | Redis (in-memory) | task lifetime | active state |
| Repository summary | Postgres + pgvector | indefinite | codebase overview |
| Execution history | Postgres | 90 days | past runs |
| Debugging patterns | Postgres + pgvector | indefinite | fix strategies |
| Code patterns | Postgres + pgvector | indefinite | style per repo |
| Failure library | Postgres + pgvector | indefinite | known failures |

---

## GitHub Integration (Part 8)

**File:** `backend/app/integrations/github_client.py`

Consolidated client supporting PAT, GitHub App, and OAuth auth. Handles:
- Repository cloning and branch management
- Push changes via GitHub API (no git needed)
- Pull request creation and commenting
- Workflow triggering, monitoring, and cancellation
- Artifact download
- Webhook signature verification

**Webhook receiver:** `backend/app/api/routes/webhooks.py`
- Endpoint: `POST /api/v1/webhooks/github`
- Supported events: `workflow_run`, `push`, `pull_request`, `check_run`, `repository`

---

## Security (Part 10)

### SecretManager
**File:** `backend/app/core/secret_manager.py`
- AES-256-GCM encryption (with XOR fallback if `cryptography` not installed)
- Secrets never in logs, query results, or API responses
- Full audit trail: store, retrieve, rotate, revoke

### RBAC
**File:** `backend/app/core/rbac.py`
- Roles: `aep:viewer`, `aep:operator`, `aep:admin`, `aep:system`
- Permissions: view, create, trigger, manage flags/secrets/tenants
- Integrated with existing auth via Compatibility Adapter

### CommandValidator
**File:** `backend/app/security/validator.py`
- Blocklists: `rm -rf /`, `dd`, `mkfs`, `chmod 777 /`, `env | grep`, `cat /etc/passwd`, `printenv`, crypto mining, destructive SQL
- Domain allowlist for network access
- Secret detection and output sanitization
- All commands logged to `aep_audit_log`

---

## Observability (Part 11)

Metrics are tracked via the existing `MetricsCollector` in `backend/app/observability/metrics.py`. AEP-specific metrics:
- `aep.task.created` / `aep.task.completed` / `aep.task.duration`
- `aep.llm.tokens` / `aep.llm.tokens_saved` / `aep.llm.latency`
- `aep.provider.used` / `aep.provider.cooldown` / `aep.provider.quota_exhausted`
- `aep.workflow.triggered` / `aep.workflow.duration` / `aep.workflow.failed`

Structured JSON logging via `structlog` with mandatory fields: `timestamp, level, service, trace_id, tenant_id, task_id, execution_id, agent, message, metadata`.

---

## Migration Phases (Part 12)

| Phase | Scope | Status | Flags Enabled |
|-------|-------|--------|---------------|
| 0 — Foundation | aep_* models, feature flags, adapter, /LLM stubs | ✅ Done | none |
| 1 — LLM Gateway | Multi-provider router, quota, compression | ✅ Done | `llm_gateway_enabled`, `compression_pipeline_enabled` |
| 2 — GitHub Integration | GitHub client, webhook receiver | ✅ Done | `webhook_receiver_enabled` |
| 3 — Single-Agent Execution | Plugin registry, GHA Runtime Manager | ✅ Done | `agent_planner_enabled`, `agent_coder_enabled`, `github_actions_runtime_enabled` |
| 4 — Memory System | Context Engine, repo indexing | ✅ Done | `memory_system_enabled` |
| 5 — Multi-Agent + Full UI | Frontend modules | ⏳ Pending | `multi_agent_enabled`, `autonomous_ui_enabled` |
| 6 — Hardening | Security, RBAC, tenant isolation | ✅ Done | `autonomous_engine_enabled` (master) |

---

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_compression.py` | 82 | ✅ All pass |
| `test_llm_gateway.py` | 11 | ✅ All pass |
| `test_security.py` | 3 | ✅ All pass |
| `test_model_router.py` | 4 | ✅ All pass |
| `test_health.py` | 1 | ✅ Pass |
| `test_workspace.py` | 1 | ✅ Pass |
| **Total** | **102** | ✅ All pass |

---

## Environment Variables

### AEP Feature Flags
```bash
AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED=false
AEP_FLAG_LLM_GATEWAY_ENABLED=false
AEP_FLAG_GITHUB_ACTIONS_RUNTIME_ENABLED=false
AEP_FLAG_AGENT_PLANNER_ENABLED=false
AEP_FLAG_AGENT_CODER_ENABLED=false
AEP_FLAG_AGENT_DEBUGGER_ENABLED=false
AEP_FLAG_MEMORY_SYSTEM_ENABLED=false
AEP_FLAG_MULTI_AGENT_ENABLED=false
AEP_FLAG_AUTONOMOUS_UI_ENABLED=false
AEP_FLAG_WEBHOOK_RECEIVER_ENABLED=false
# compression_pipeline_enabled defaults to true
```

### LLM Provider API Keys

No API keys are required as environment variables. The AEP LLM Gateway reads them from the user's encrypted `user_llm_providers` table at request time. Configure providers via the existing **Settings → My Providers** UI or the `POST /api/v1/llm-providers` endpoint.

### GitHub Integration
```bash
GITHUB_TOKEN=...
GITHUB_WEBHOOK_SECRET=...
AEP_PLATFORM_URL=https://sivasbrmni-devbuddy.hf.space
AEP_EXECUTION_TOKEN=...
```
