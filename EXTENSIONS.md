# DevBuddy — Extension Points & AEP Layer

This document describes how the **Autonomous Engineering Platform (AEP)** attaches to the existing DevBuddy application without modifying its core. It is the authoritative catalogue of extension seams established in **Phase 0** and is the contract that later phases extend.

If you are adding a new agent, hook, or flag, read this first.

---

## Table of contents

1. [Phase status](#phase-status)
2. [Architectural rule: additive only](#architectural-rule-additive-only)
3. [Feature flags](#feature-flags)
4. [Compatibility Adapter Layer](#compatibility-adapter-layer)
5. [Plugin registry & `AgentPlugin` interface](#plugin-registry--agentplugin-interface)
6. [`/LLM` gateway contract](#llm-gateway-contract)
7. [`aep_*` database tables](#aep_-database-tables)
8. [Admin & diagnostic endpoints](#admin--diagnostic-endpoints)
9. [Adding a new agent (cheatsheet)](#adding-a-new-agent-cheatsheet)
10. [GCP deployment notes (devbuddy.org)](#gcp-deployment-notes-devbuddyorg)

---

## Phase status

| Phase | Description | Status |
|------:|-------------|--------|
| 0 | Foundation: tables, flags, adapter, plugin registry, `/LLM` stub | **shipped** (this PR) |
| 1 | LLM gateway → real Ollama | not started |
| 2 | GitHub client + webhook receiver | not started |
| 3 | Planner + Coder agents + GHA runtime | not started |
| 4 | Memory system + pgvector | not started |
| 5 | All remaining agents + frontend module | not started |
| 6 | Hardening, RBAC, audit, tenant isolation | not started |

Every feature flag in Phase 0 defaults to **off**. The repo is mergeable with zero observable behavior change for existing users.

---

## Architectural rule: additive only

Three rules apply to every change in the AEP layer:

1. **No destructive schema changes.** Every new table uses the `aep_` prefix. Existing tables (`tasks`, `agent_executions`, `audit_logs`, `agent_memories`, …) are never altered.
2. **No breaking API changes.** Every new endpoint is additive. Existing endpoints keep their contract.
3. **No forced activation.** Every capability is behind a feature flag that defaults off. The `autonomous_engine_enabled` master flag is the single switch that authorises any AEP behavior; it is also off by default.

When in doubt, branch and stay off the existing code paths.

---

## Feature flags

Defined in `backend/app/aep/feature_flags.py`. Every flag is registered with a `FlagSpec` so it shows up in the admin UI automatically.

Resolution precedence (first match wins):

1. Per-tenant DB row in `aep_feature_flags` (`tenant_id` set)
2. Global DB row in `aep_feature_flags` (`tenant_id IS NULL`)
3. Environment variable `AEP_FLAG_<UPPER_NAME>` (truthy values: `1`, `true`, `yes`, `on`, `enabled`)
4. The `FlagSpec.default` value

If `autonomous_engine_enabled` is `false`, every capability flag is forced `false`, regardless of its own value. The only flags that bypass this gate are the master flag itself and `human_approval_required` (safety default `true`).

The registered flags:

| Flag | Default | Phase | Effect when on |
|------|--------:|------:|----------------|
| `autonomous_engine_enabled`     | `false` | 6 | Master switch for the AEP layer. |
| `llm_gateway_enabled`           | `false` | 1 | `/LLM/*` routes proxy to Ollama instead of returning 503. |
| `webhook_receiver_enabled`      | `false` | 2 | `/api/v1/aep/webhooks/github` accepts GitHub events. |
| `github_actions_runtime_enabled`| `false` | 3 | GHA Runtime Manager may generate workflow YAML and trigger runs. |
| `agent_planner_enabled`         | `false` | 3 | Loads the Planner agent. |
| `agent_coder_enabled`           | `false` | 3 | Loads the Coder agent. |
| `agent_debugger_enabled`        | `false` | 5 | Loads the Debugger agent. |
| `agent_tester_enabled`          | `false` | 5 | Loads the Tester agent. |
| `agent_reviewer_enabled`        | `false` | 5 | Loads the Reviewer agent. |
| `agent_security_audit_enabled`  | `false` | 5 | Loads the Security Audit agent. |
| `agent_documentation_enabled`   | `false` | 5 | Loads the Documentation agent. |
| `agent_devops_enabled`          | `false` | 5 | Loads the DevOps agent. |
| `memory_system_enabled`         | `false` | 4 | Activates the long-term memory store + Context Engine. |
| `multi_agent_enabled`           | `false` | 5 | Activates the Coordinator agent + multi-agent orchestration. |
| `autonomous_ui_enabled`         | `false` | 5 | Mounts the AEP frontend module. |
| `human_approval_required`       | `true`  | 0 | Executions pause at `AWAITING_APPROVAL` before destructive ops. **Defaults true for safety.** |

### Programmatic use

```python
from app.aep.feature_flags import get_feature_flag_service

ff = get_feature_flag_service()
if await ff.is_enabled("llm_gateway_enabled", tenant_id=tenant.id, db=db):
    ...
```

The service caches resolved values in-process with a 5 s TTL; calls to `FeatureFlagService.set` invalidate the cache automatically.

---

## Compatibility Adapter Layer

Defined in `backend/app/aep/compat/adapter.py`. The adapter holds an ordered set of hooks per *channel*; existing services call `dispatch_*` at well-defined seams. Hook failures are logged and swallowed — they must never break the host request.

### Channels

| Channel | Payload type | Where it fires |
|---------|--------------|----------------|
| `pre_task_create`      | `TaskCreatePayload`     | before `task_service.create_task` |
| `post_task_create`     | `TaskCreatePayload`     | after `task_service.create_task`  |
| `pre_state_transition` | `StateTransitionPayload`| before any task FSM transition    |
| `post_state_transition`| `StateTransitionPayload`| after any task FSM transition     |
| `pre_llm_call`         | `LlmCallPayload`        | before invoking an LLM provider   |
| `post_llm_call`        | `LlmCallPayload`        | after an LLM provider returns     |

### Registering a hook

```python
from app.aep.compat import get_compatibility_adapter, LlmCallPayload

adapter = get_compatibility_adapter()

@adapter.on_pre_llm_call
async def my_hook(payload: LlmCallPayload) -> None:
    # observe / annotate; never raise
    ...
```

Sync callables are allowed; the adapter awaits them if they return a coroutine.

### Wiring existing services (Phase 1+)

In Phase 0 the dispatchers exist but no existing service calls them. Phase 1+ wires them in at the minimum-impact location of each existing service. The hooks will be invoked from:

- `app/services/task_service.py` — `create_task`, `transition_task_state`
- `app/services/llm_service.py` — every `_call_*` provider entry point

This is intentionally deferred to Phase 1 so this PR contains zero behavior change.

---

## Plugin registry & `AgentPlugin` interface

Defined in `backend/app/aep/plugins/`.

### Contract

Every agent extends `AgentPlugin` (see `app/aep/plugins/base.py`) and must declare four class-level constants:

```python
from app.aep.plugins import AgentPlugin, AgentInput, AgentOutput

class MyAgent(AgentPlugin):
    name = "my_agent"
    feature_flag = "agent_my_agent_enabled"
    model = "gemma4:31b-cloud"
    description = "Does the thing."

    async def execute(self, input: AgentInput) -> AgentOutput:
        ...
```

`__init_subclass__` enforces the contract — a subclass that omits any of `name`, `feature_flag`, or `model` raises `TypeError` at import time.

### Activation lifecycle

1. The FastAPI `lifespan` hook calls `PluginRegistry.discover()` on startup.
2. `discover` imports every submodule of `app.aep.plugins.agents`. Each module typically calls `get_plugin_registry().register(MyAgent)` at module top-level.
3. For every registered class, the registry consults `FeatureFlagService.is_enabled(cls.feature_flag)`. If true, an instance is created and kept in the active set.
4. The registry can be re-activated at any time via `PluginRegistry.activate_registered()` — useful after toggling flags from the admin API.

In Phase 0 the `app/aep/plugins/agents/` package is empty; `discover` returns an empty list.

### Inputs and outputs

`AgentInput` and `AgentOutput` are Pydantic v2 models defined in `app/aep/plugins/types.py`. They are the wire format between the Coordinator (Phase 5) and individual agents; they also serialise to the WebSocket layer for live UI updates.

---

## `/LLM` gateway contract

Mounted at the application root (no `/api/v1` prefix) per AEP spec §2.2.

| Method | Path           | Phase 0 behavior |
|--------|----------------|------------------|
| GET    | `/LLM/health`  | Public. Returns `200 {"status":"ok"}` when `llm_gateway_enabled` is on, else `503 {"status":"disabled", ...}`. |
| POST   | `/LLM/generate`| Auth required. `503 GatewayErrorEnvelope` until Phase 1. |
| POST   | `/LLM/chat`    | Auth required. `503 GatewayErrorEnvelope` until Phase 1. |
| POST   | `/LLM/embed`   | Auth required. `503 GatewayErrorEnvelope` until Phase 1. |
| POST   | `/LLM/route`   | Auth required. `503 GatewayErrorEnvelope` until Phase 1. |
| GET    | `/LLM/models`  | Auth required. `503 GatewayErrorEnvelope` until Phase 1. |

The 503 envelope is stable:

```json
{
  "error": "service_unavailable",
  "phase": "phase_0",
  "message": "AEP LLM gateway is not enabled. ...",
  "flag": "llm_gateway_enabled",
  "timestamp": "2026-05-26T17:00:00+00:00"
}
```

The response also sets `X-AEP-Phase: phase_0` and `X-AEP-Flag: llm_gateway_enabled` for monitoring.

Phase 1 replaces every endpoint body with a real Ollama proxy. The request/response schemas (`GenerateRequest`, `ChatRequest`, `EmbedRequest`, `RouteRequest`) defined in `app/aep/api/llm_gateway.py` are the **stable contract** clients can integrate against today.

---

## `aep_*` database tables

Created by Alembic migration `003_aep_foundation.py`. Every table is additive, FK-cascaded to `tenants`, indexed by `tenant_id`, and reversible via `downgrade()`.

| Table | Purpose |
|-------|---------|
| `aep_feature_flags` | Per-tenant + global feature flag overrides. |
| `aep_repositories` | Registered repos the AEP can operate on. |
| `aep_executions` | Top-level AEP execution records (distinct from existing `agent_executions`). |
| `aep_execution_steps` | One row per agent invocation within an execution. |
| `aep_agent_plans` | Planner agent output (DAG, agent assignments, estimated cost). |
| `aep_workflow_runs` | GitHub Actions runs triggered by the AEP. |
| `aep_memory_entries` | Long-term memory entries (Phase 4 wires pgvector). |
| `aep_audit_log` | Hash-chained AEP-specific audit trail. |
| `aep_secrets_metadata` | Metadata-only — plaintext values live in an external secret manager. |

### Adding a new `aep_*` table

1. Add a SQLAlchemy model to `app/aep/models.py`.
2. Generate a new Alembic revision (`alembic revision -m "..."`) and write `upgrade()` + `downgrade()`.
3. The new model is picked up automatically because `app/main.py` imports `app.aep.models`, registering the class with `Base.metadata`.

---

## Admin & diagnostic endpoints

Mounted at `/api/v1/aep`:

| Method | Path                       | Purpose |
|--------|----------------------------|---------|
| GET    | `/api/v1/aep/flags`        | List every flag and its resolved value. Optional `tenant_id` query for per-tenant view. |
| PUT    | `/api/v1/aep/flags/{name}` | Toggle a flag globally or per-tenant. Requires `aep:admin` role on the JWT (bootstrap mode allows any authenticated user when no role claim is present). |
| GET    | `/api/v1/aep/plugins`      | List every registered plugin and its active/inactive state. |
| GET    | `/api/v1/aep/status`       | Summary stats for dashboards. |

These routes work even when the master flag is off — administration controls the capabilities, not the other way around.

---

## Adding a new agent (cheatsheet)

This will become the standard pattern from Phase 3 onwards.

1. **Add a flag** to `FLAGS` in `backend/app/aep/feature_flags.py` (default `false`).
2. **Create the agent module** in `backend/app/aep/plugins/agents/<name>.py`:
   ```python
   from app.aep.plugins import AgentPlugin, AgentInput, AgentOutput, get_plugin_registry

   class MyAgent(AgentPlugin):
       name = "my_agent"
       feature_flag = "agent_my_agent_enabled"
       model = "gemma4:31b-cloud"
       description = "..."

       async def execute(self, input: AgentInput) -> AgentOutput:
           ...

   get_plugin_registry().register(MyAgent)
   ```
3. **Restart the backend**. The `lifespan` hook re-runs `PluginRegistry.discover()`. If the flag is on, the agent goes active.
4. **No host code changes are required**. Existing routers don't need to know about the new agent — it's reached through the registry only.

---

## GCP deployment notes (devbuddy.org)

The Phase 0 layer is deployment-neutral; it adds tables and dormant routes that work on any Postgres-compatible database. The repo already targets GCP via `DEPLOY_GCP.md` (single-VM Docker Compose on `devbuddy.org`).

Notes for later phases:

- **Phase 4 (memory + pgvector).** The Phase 0 schema stores embeddings as `TEXT` (JSON-encoded float array). Phase 4 enables the `vector` extension and migrates the column type. Both Supabase Postgres and Cloud SQL for PostgreSQL support pgvector out of the box; the in-container Postgres in `docker-compose.prod.yml` needs the `pgvector/pgvector:pg16` image swap.
- **Phase 1 (Ollama).** A `gemma4:31b-cloud`-class model will not run on an `e2-micro` VM. Options:
  - GCE VM with GPU (`n1-standard-4` + T4, or `g2-standard-4` + L4) — the spec's literal requirement.
  - Drop down to a smaller quantised model (`llama3.1:8b`, `qwen2.5-coder:7b`) for the dev/staging environment and keep the 31B model for production-only.
  - Self-host Ollama on a separate GPU instance and point `OLLAMA_URL` at it from the e2-micro app VM.
- **Cloud SQL vs container Postgres.** Both are supported. Cloud SQL gives you automated backups, point-in-time recovery, and survives VM rebuilds; the container approach is cheaper but is a single point of failure. The decision should be made before Phase 4 ships, because re-pointing the AEP at a new database mid-migration is annoying.

---

## See also

- `backend/alembic/versions/003_aep_foundation.py` — schema migration
- `backend/app/aep/feature_flags.py` — flag registry & resolution
- `backend/app/aep/compat/adapter.py` — hook system
- `backend/app/aep/plugins/` — plugin registry + `AgentPlugin` base class
- `backend/app/aep/api/llm_gateway.py` — `/LLM` namespace contract
- `backend/app/aep/api/admin.py` — `/api/v1/aep/*` admin routes
- `backend/tests/aep/` — Phase 0 test suite
