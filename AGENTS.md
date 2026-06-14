# AGENTS.md — DevBuddy Autonomous Engineering Platform (AEP)

> **Audience.** This file is the single handoff document for any AI coding
> agent (Devin, Cursor, Claude Code, Copilot Workspace, …) or human
> contributor working on the Autonomous Engineering Platform layer of
> DevBuddy. Read this file first. It tells you what is implemented, what
> is not, what the contracts are, and where to start the next phase.
>
> **Authoritative spec.** The implementation contract is the
> *Autonomous AI Software Engineering Platform — Implementation
> Specification* (14 parts) provided by the project owner. This document
> summarises and tracks that spec. When in doubt, the spec wins; flag any
> deviation in a PR description.

---

## Table of contents

1. [Ground rules](#ground-rules)
2. [Phase status at a glance](#phase-status-at-a-glance)
3. [What is implemented today](#what-is-implemented-today)
4. [What is pending — by phase](#what-is-pending--by-phase)
5. [Repository map](#repository-map)
6. [Feature flags](#feature-flags)
7. [Environment variables](#environment-variables)
8. [Local development & verification](#local-development--verification)
9. [Conventions & guardrails](#conventions--guardrails)
10. [Open decisions (need owner input)](#open-decisions-need-owner-input)
11. [Related documents](#related-documents)

---

## Ground rules

These rules come from spec §1.2 (Hard Constraints) and are
**non-negotiable**:

1. **No destructive schema changes.** Every new table uses the `aep_`
   prefix. Existing tables (`tenants`, `users`, `tasks`, `task_events`,
   `agent_executions`, `audit_logs`, `agent_memories`, …) are never
   altered. Touching them requires explicit owner approval.
2. **No breaking API changes.** Every new endpoint is additive. Existing
   endpoints under `/api/v1/*` keep their request/response contracts.
3. **No forced activation.** Every capability ships behind a feature
   flag that defaults **off**. The master flag
   `autonomous_engine_enabled` is the single switch authorising any AEP
   behaviour; it is also off by default. A fresh install must behave
   identically to pre-AEP DevBuddy.
4. **No persistent compute workers for agent execution.** GitHub Actions
   runners are the only approved ephemeral execution environment
   (spec §1.2, §5). Do not introduce a Kubernetes Job, Celery worker, or
   long-running Docker container for running agents.
5. **No external LLM dependencies.** All inference goes through the
   `/LLM` gateway, which proxies to a self-hosted Ollama instance **or**
   to Ollama Cloud via `OLLAMA_CLOUD_API_KEY`. No direct OpenAI /
   Anthropic / Groq calls from AEP code. (The legacy
   `app/services/llm_service.py` keeps its multi-provider support for
   non-AEP code paths; AEP code must use the gateway.)
6. **No secrets in plaintext.** Never log, return, or commit API keys,
   GitHub tokens, or JWT secrets. The `aep_secrets_metadata` table
   stores only metadata; ciphertext lives in the secret manager
   (Phase 6).
7. **Backward compatibility is the prime directive.** When a hook or
   service has no handler registered, it must be a no-op. Errors in AEP
   code must never break a host request.

If you are about to violate one of these rules, **stop** and surface the
question to the owner via a PR comment or message.

---

## Phase status at a glance

| Phase | Description                                                            | Status                        | PR        |
|------:|------------------------------------------------------------------------|-------------------------------|-----------|
| **0** | Foundation: tables, flags, adapter, plugin registry, `/LLM` stub        | **Shipped (merged)**          | [#1](https://github.com/SivaSbrmni/devbuddy/pull/1) |
| **1** | LLM Gateway → real Ollama (local + Ollama Cloud)                        | **Shipped (merged)**          | [#2](https://github.com/SivaSbrmni/devbuddy/pull/2) |
| **2** | GitHub integration: client, webhook receiver, repo registration        | **Shipped (merged)**          | [#8](https://github.com/SivaSbrmni/devbuddy/pull/8) |
| **3** | Single-agent execution: Planner + Coder + GHA Runtime Manager           | **Shipped (merged)**          | [#8](https://github.com/SivaSbrmni/devbuddy/pull/8) |
| **4** | Memory & Context Engine: pgvector, repo indexing, retrieval             | **Shipped (merged)**          | [#8](https://github.com/SivaSbrmni/devbuddy/pull/8) |
| **5** | Remaining agents (Debugger, Tester, Reviewer, Security, Docs, DevOps), Coordinator FSM, full UI | **Shipped (merged)**          | [#8](https://github.com/SivaSbrmni/devbuddy/pull/8), [#9](https://github.com/SivaSbrmni/devbuddy/pull/9) |
| **6** | Hardening: SecretManager, CommandValidator, RBAC, tenant isolation, observability | **Shipped (merged)**          | [#8](https://github.com/SivaSbrmni/devbuddy/pull/8) |

Spec checklist mapping → see *Part 13* of the spec. Every checked-off
item in this document corresponds to a checklist line in §13.

---

## What is implemented today

### Phase 0 — Foundation (merged, PR #1)

**Database** — Alembic migration
`backend/alembic/versions/003_aep_foundation.py` creates 9 additive
tables, all prefixed `aep_`, all `tenant_id`-scoped, all reversible:

| Table                  | Purpose                                                |
|------------------------|--------------------------------------------------------|
| `aep_feature_flags`    | Per-tenant + global feature flag overrides.            |
| `aep_repositories`     | Registered repos available to AEP execution.           |
| `aep_executions`       | Top-level execution record (one per task submission).  |
| `aep_execution_steps`  | Per-step record inside an execution (DAG nodes).       |
| `aep_agent_plans`      | Planner output: structured execution DAG.              |
| `aep_workflow_runs`    | GitHub Actions workflow run tracking.                  |
| `aep_memory_entries`   | Long-term memory entries (embeddings stored as TEXT in Phase 0; migrated to `vector` in Phase 4). |
| `aep_audit_log`        | Hash-chained audit events for AEP-originated actions.  |
| `aep_secrets_metadata` | Metadata only — never plaintext ciphertext.            |

SQLAlchemy models live in `backend/app/aep/models.py` and follow the
existing patterns (`Mapped`, `mapped_column`, UUID PKs).

**Feature flag service** — `backend/app/aep/feature_flags.py`
- 16 registered flags, every capability flag defaults `false`.
- Resolution precedence: per-tenant DB row → global DB row → env var
  `AEP_FLAG_<UPPER>` → `FlagSpec.default`.
- Master flag `autonomous_engine_enabled` forces every non-independent
  capability flag to `false` when off.
- `human_approval_required` defaults `true` (safety).

**Compatibility Adapter Layer** —
`backend/app/aep/compat/adapter.py` with 6 hook channels:
`pre/post_task_create`, `pre/post_state_transition`, `pre/post_llm_call`.
All channels are empty in Phase 0; the dispatcher is a no-op when no
hooks are registered. Hook failures are logged and swallowed.

**Plugin registry** — `backend/app/aep/plugins/registry.py`
- `AgentPlugin` ABC with required class attrs (`name`, `feature_flag`,
  `model`, `fallback_model`, `description`) enforced via
  `__init_subclass__`.
- `PluginRegistry.discover()` imports submodules under
  `app/aep/plugins/agents/` and activates plugins whose feature flag is
  on. In Phase 0 the `agents/` directory is empty by design.

**Admin endpoints** at `/api/v1/aep` —
`backend/app/aep/api/admin.py`:
- `GET /flags`, `PUT /flags/{name}` — list / toggle flags.
- `GET /plugins` — registered plugins, active state.
- `GET /status` — summary stats.

**`/LLM` gateway stub** — `backend/app/aep/api/llm_gateway.py` (Phase 0
behaviour): six routes mounted at the application root (no `/api/v1`
prefix, per spec §2.2). Every route returns a structured `503` envelope
when `llm_gateway_enabled` is off. Wired into `app/main.py`.

**Observability shim** — `backend/app/aep/observability.py` exposes
`aep_logger(component)` returning a structlog logger bound to
`aep_component=<name>`. Metrics + tracing land in Phase 6.

**Docs** — `EXTENSIONS.md` at the repo root documents every flag,
channel, route, table, and the AgentPlugin contract.

---

### Phase 1 — LLM Gateway (functional, draft PR #2)

> **Status.** Code complete. Router has unit tests (23 cases). Client +
> gateway service + route-level tests intentionally **not written**
> (owner directive: limit on test work). Functional behaviour verified
> by hand: imports clean, lint clean, 56 AEP + 10 smoke tests still
> pass, flag defaults still off so zero behaviour change at merge.

**New subpackage** — `backend/app/aep/llm/`:

| Module             | Role                                                                                                              |
|--------------------|-------------------------------------------------------------------------------------------------------------------|
| `config.py`        | `AepLlmConfig` dataclass. Env-driven. Falls back to existing `OLLAMA_URL` setting. Auth via `OLLAMA_CLOUD_API_KEY`. |
| `errors.py`        | Exception hierarchy: `LlmGatewayError`, `UpstreamUnavailable`, `UpstreamTimeout`, `UpstreamHttpError`, `ModelNotFound`, `InvalidRequest`. Each maps to an HTTP status. |
| `router.py`        | `ModelRouter` implementing spec §2.5 routing + spec §2.4 fallback table. Overridable via `AEP_MODEL_FOR_<TASK_TYPE>` env vars. |
| `ollama_client.py` | Async `httpx` client speaking the native Ollama surface (`/api/{generate,chat,embeddings,tags}`). Retries with exponential backoff on network errors + 5xx. Streaming via async generators. Strict status → exception translation. |
| `gateway.py`       | `LlmGatewayService` façade. Owns model resolution, token accounting, structured logging (`aep.llm.call`), and `pre/post_llm_call` adapter dispatch. |

**`/LLM/*` routes wired** — when `llm_gateway_enabled=true`:

| Method | Path           | On (Phase 1)                                                          |
|--------|----------------|-----------------------------------------------------------------------|
| GET    | `/LLM/health`  | Probes upstream Ollama; returns base URL, model count, cloud flag.    |
| POST   | `/LLM/generate`| Proxies to `/api/generate`. `stream=true` returns SSE.                |
| POST   | `/LLM/chat`    | Proxies to `/api/chat`. `stream=true` returns SSE.                    |
| POST   | `/LLM/embed`   | Proxies to `/api/embeddings` once per input string.                   |
| POST   | `/LLM/route`   | Returns `{task_type, model, fallback, source}`.                       |
| GET    | `/LLM/models`  | Returns upstream model list + default model + routing snapshot.       |

When the flag is off, every route returns the same `503` envelope as
Phase 0 (the phase string in the envelope is now `phase_1`). The
contract clients integrate against is **unchanged** between phases.

**Streaming SSE format** —

```
data: {"model":"gemma4:31b-cloud","delta":"…token…","done":false,"prompt_tokens":123,"completion_tokens":17}

```

Errors during a stream surface as a final `event: error` SSE frame.

**Deployment** — `docker-compose.yml` (dev) and
`docker-compose.prod.yml` (GCP VM) now ship an `ollama` sidecar on the
internal Docker network. Backend reaches it as `http://ollama:11434`
(never exposed publicly). Model cache: named volume `ollama_data` (dev)
or bind mount to `${DATA_ROOT}/ollama` (prod) so models survive VM
reboots.

**Cloud mode** — setting `OLLAMA_CLOUD_API_KEY` causes the backend to
attach `Authorization: Bearer <key>` to every upstream call. Point
`AEP_OLLAMA_BASE_URL` at Ollama Cloud (or any remote Ollama-compatible
host) and the local sidecar can be skipped entirely.

**EXTENSIONS.md** updated with the Phase 1 contract: env var reference,
routing table, SSE envelope, error envelope, override precedence,
Docker topology + GCP cloud-mode notes.

---

## What is pending — by phase

Each phase below corresponds to spec §12.1 and §13. Land each phase as
one or more PRs targeting `scaffold/initial-platform` (or whatever the
current integration branch is). Keep PRs reviewable — split if a phase
would exceed ~1500 lines of diff.

### Phase 1 — Remaining items (to close PR #2 ready-for-review)

- [ ] Decide & confirm Ollama Cloud auth header convention
      (`Authorization: Bearer <key>` is the current default). Adjust
      `AepLlmConfig.auth_headers()` if Ollama Cloud uses
      `X-API-Key` or similar.
- [ ] Decide & confirm the exact model tag for the spec's
      `gemma4:31b-cloud`. If Ollama Cloud exposes it under a different
      name (e.g. `gpt-oss:120b-cloud`, `gemma2:27b-cloud`), update
      `AepLlmConfig.default_model` and the routing table in
      `SPEC_DEFAULT_MAPPING`.
- [ ] Optional: pre-pull the default model on first container start.
      Add a `docker-entrypoint`-style script that runs
      `ollama pull "$AEP_DEFAULT_MODEL"` once if `OLLAMA_CLOUD_API_KEY`
      is unset (i.e. local mode only).
- [ ] Optional: wire `pre/post_llm_call` hooks to persist token usage
      into `aep_audit_log` for observability. (Currently the hooks fire
      but no listener is attached.)

### Phase 2 — GitHub integration

Spec sections: §8, §13 (rows 7–8). Flags: `webhook_receiver_enabled`.

- [x] **GitHub client** — `backend/app/aep/github/client.py`. Abstract
      base + three concrete implementations:
    - `GitHubAppClient` (preferred — installation tokens, 5–15k req/hr)
    - `PersonalAccessTokenClient` (dev-friendly fallback)
    - `OAuthClient` (used when acting on behalf of a logged-in user)
      All implementations share an interface (`get_repo`, `list_files`,
      `read_file`, `write_file`, `create_branch`, `open_pull_request`,
      `list_workflow_runs`, `get_workflow_run_logs`,
      `download_workflow_artifact`, `dispatch_workflow`, …) — see
      spec §8.2.
- [x] **Webhook receiver** — `backend/app/aep/api/github_webhooks.py`
      mounted at `/api/v1/aep/webhooks/github`. Verify HMAC signature
      using the per-repo secret stored in `aep_repositories`. Route
      events to an in-process `WebhookEventRouter`. Events to handle
      (spec §8.3): `pull_request`, `push`, `workflow_run`,
      `check_run`, `issue_comment`, `pull_request_review`,
      `installation`, `installation_repositories`.
- [x] **Repository registration API** —
      `POST /api/v1/aep/repositories` and friends. Stores rows in
      `aep_repositories`. Validates that the integration credentials
      have the right scopes (`contents:write`, `pull_requests:write`,
      `actions:read`).
- [x] Wire `webhook_receiver_enabled` flag.
- [x] Add tests for HMAC verification and the event router (one test
      per event type at minimum).
- [x] Document the GitHub App manifest / setup in
      `docs/aep-github-app-setup.md` (referenced from EXTENSIONS.md).

### Phase 3 — Single-agent execution

Spec sections: §5, §6 (Planner + Coder only), §13 rows 9–12. Flags:
`agent_planner_enabled`, `agent_coder_enabled`,
`github_actions_runtime_enabled`.

- [x] **GHA Runtime Manager** — `backend/app/aep/gha/runtime.py`.
    - YAML generator: takes an `AgentPlan` step and emits a workflow
      file matching the template in spec §5.2.
    - Trigger: pushes the generated workflow to a feature branch and
      calls `workflow_dispatch` via the GitHub client.
    - Monitor: long-polls `workflow_run` events from the webhook
      receiver (Phase 2) and reflects state into `aep_workflow_runs`.
    - Log streaming: download partial logs via the GitHub API and
      stream to WebSocket subscribers (Phase 5 UI).
- [x] **Planner agent** —
      `backend/app/aep/plugins/agents/planner.py`. Subclasses
      `AgentPlugin`. Takes a raw task description; produces an
      `ExecutionPlan` JSON (spec §6.1 Planner). Uses
      `gemma4:31b-cloud` via the gateway. Persists output to
      `aep_agent_plans`.
- [x] **Coding agent** —
      `backend/app/aep/plugins/agents/coder.py`. Reads the plan,
      generates diffs/new files, writes a commit, opens a PR via the
      GitHub client. Falls back to `deepseek-coder` per spec §6.1.
- [x] **State machine** — implement the FSM transitions in spec §6.2
      (`PENDING → PLANNING → AWAITING_APPROVAL → EXECUTING → … → DONE
      | FAILED | CANCELLED`). Each transition writes a row to
      `aep_execution_steps` and dispatches
      `pre/post_state_transition` adapter hooks.
- [x] **Human-in-the-loop approval gate.** When
      `human_approval_required=true` (default), the FSM pauses at
      `AWAITING_APPROVAL` until an admin endpoint approves or rejects
      the plan.
- [x] End-to-end happy path: submit task → Planner produces plan →
      operator approves → Coder pushes branch → GHA workflow runs →
      PR opened. Document the test plan in EXTENSIONS.md.

### Phase 4 — Memory system

Spec sections: §7, §13 rows 16–17. Flags: `memory_system_enabled`.

- [x] Enable pgvector. Migration `004_pgvector_enable.py`:
      `CREATE EXTENSION IF NOT EXISTS vector;` (no-op on Supabase /
      Cloud SQL with pgvector pre-enabled).
- [x] Migration `005_aep_memory_vectorise.py`: alter
      `aep_memory_entries.embedding` from `TEXT` to `vector(N)` where
      `N` matches the embedding model dimension (768 for
      `nomic-embed-text`, 1536 for some others). Re-encode existing
      rows during migration; downgrade reverts to TEXT.
- [x] **Context Engine** — `backend/app/aep/memory/context_engine.py`.
    - Repository indexing job: clone, parse AST, summarise files via
      `/LLM/chat` with the Documentation Agent's model, embed via
      `/LLM/embed`, persist to `aep_memory_entries`.
    - Incremental re-index on webhook `push` events.
    - Token-budget-aware retrieval: KNN over embeddings, then
      priority-ranked truncation.
- [x] **Memory service** — `backend/app/aep/memory/service.py` with
      typed methods: `store_working_context`, `recall_working_context`,
      `index_repository`, `retrieve_similar`, `store_failure_pattern`,
      `lookup_fix_strategy`. Working context uses Redis with key
      `aep:{tenant_id}:working:{execution_id}`.
- [x] Redis dependency: add to docker-compose. Document the cache vs
      durable split (Redis is per-task scratch; Postgres+pgvector is
      durable).

### Phase 5 — Remaining agents, Coordinator, UI

Spec sections: §6 (Debugger, Tester, Reviewer, Security, Docs, DevOps,
Coordinator), §6.3, §9, §13 rows 13–24. Flags: `agent_debugger_enabled`,
`agent_tester_enabled`, `agent_reviewer_enabled`,
`agent_security_audit_enabled`, `agent_documentation_enabled`,
`agent_devops_enabled`, `multi_agent_enabled`, `autonomous_ui_enabled`.

- [x] **Debugger agent** — `plugins/agents/debugger.py`. Reads test
      logs, traces root cause, applies fix patches, iterates up to a
      configurable retry count.
- [x] **Tester agent** — `plugins/agents/tester.py`. Writes unit /
      integration tests; runs them; parses results; reports coverage
      delta.
- [x] **Reviewer agent** — `plugins/agents/reviewer.py`. Reviews
      generated diffs; comments on the PR; produces a severity-ranked
      issue list.
- [x] **Security Audit agent** — `plugins/agents/security_audit.py`.
      Scans for vulnerabilities, secret leakage, injection,
      dependency issues.
- [x] **Documentation agent** — `plugins/agents/documentation.py`.
      Uses `mistral:7b` per spec §6.1.
- [x] **DevOps agent** — `plugins/agents/devops.py`. Generates or
      modifies CI/CD config, Dockerfiles, infra-as-code.
- [x] **Coordinator agent** — `plugins/agents/coordinator.py` +
      orchestrator service. Owns the multi-agent DAG, routes
      `AgentMessage` envelopes via Redis pubsub, persists state to
      `aep_executions`.
- [x] **Multi-agent coordination protocol** — spec §6.3
      `AgentMessage` schema, shared memory slot, predecessor-output
      reads.
- [x] **Frontend module** — `frontend/src/aep/`. Mountable, isolated
      from existing pages, behind `autonomous_ui_enabled`. Required
      views (spec §9.1): Task Submission, Task Dashboard, Workflow
      Graph, Execution Timeline, Live Log Viewer, Diff Viewer,
      Repository Browser, PR Preview, Memory Inspector, Agent
      Activity Feed, Reasoning Trace, Approval Gate UI.
- [x] **Real-time layer** — WebSocket for agent state changes and log
      streaming; SSE for LLM token streaming in the reasoning trace
      view.

### Phase 6 — Hardening

Spec sections: §10, §11, §13 rows 18–21. Flag: `autonomous_engine_enabled`
master switch finally flips on by default for opted-in tenants.

- [x] **SecretManager** — `backend/app/aep/security/secrets.py` with
      AES-256 encryption at rest, unified `set/get/rotate/delete`
      interface, integration with GitHub Secrets for workflow
      injection, write metadata to `aep_secrets_metadata`. Never log
      plaintext.
- [x] **CommandValidator** —
      `backend/app/aep/security/command_validator.py`. Blocklists
      from spec §10.2. Every shell command injected into a workflow
      YAML passes through this validator and the result is logged to
      `aep_audit_log`.
- [x] **RBAC middleware** — `backend/app/aep/security/rbac.py`. Four
      roles (`aep:viewer`, `aep:operator`, `aep:admin`, `aep:system`).
      Integrates with the existing JWT auth via the Compatibility
      Adapter.
- [x] **Tenant isolation enforcement.** Add a SQLAlchemy event
      listener that asserts every `aep_*` query includes a `tenant_id`
      filter. Add Postgres RLS policies on every `aep_*` table.
      Namespace every Redis key under `aep:{tenant_id}:…`.
- [x] **Observability** — metrics (Prometheus), structured logging
      (already in place via structlog → Loki), distributed tracing
      (OpenTelemetry) propagated through API → Orchestrator → Agent
      → LLM Gateway → Ollama, and webhook handlers.
- [x] **Load + security audit.** Document results and remediation in
      `docs/aep-hardening-report.md`.

---

## Repository map

```
.
├── EXTENSIONS.md                        # Public contract: flags, hooks, routes, tables
├── AGENTS.md                            # THIS FILE — agent handoff doc
├── docker-compose.yml                   # Dev stack incl. `ollama` sidecar (Phase 1)
├── docker-compose.prod.yml              # GCP VM stack incl. `ollama` sidecar
├── DEPLOY_GCP.md                        # GCP topology notes
├── backend/
│   ├── alembic/versions/
│   │   └── 003_aep_foundation.py        # Phase 0 — additive aep_* tables
│   ├── app/
│   │   ├── main.py                      # FastAPI app — AEP routers mounted here
│   │   └── aep/                         # 🆕 AEP layer
│   │       ├── __init__.py
│   │       ├── feature_flags.py         # Flag service + FlagSpec registry
│   │       ├── models.py                # SQLAlchemy ORM for aep_* tables
│   │       ├── observability.py         # aep_logger() — structlog wrapper
│   │       ├── api/
│   │       │   ├── admin.py             # /api/v1/aep/{flags,plugins,status}
│   │       │   └── llm_gateway.py       # /LLM/{health,generate,chat,embed,route,models}
│   │       ├── compat/
│   │       │   └── adapter.py           # 6 hook channels, no-op until subscribed
│   │       ├── plugins/
│   │       │   ├── base.py              # AgentPlugin ABC + contract enforcement
│   │       │   ├── registry.py          # Discovery + activation
│   │       │   ├── types.py             # AgentMessage / AgentInput / AgentOutput
│   │       │   └── agents/              # Empty in Phase 0; agents land in Phases 3/5
│   │       └── llm/                     # 🆕 Phase 1 — Ollama integration
│   │           ├── config.py            # AepLlmConfig (env-driven)
│   │           ├── errors.py            # Exception hierarchy
│   │           ├── router.py            # Task-type → model routing (spec §2.5)
│   │           ├── ollama_client.py     # Async httpx client for /api/*
│   │           └── gateway.py           # LlmGatewayService façade
│   └── tests/aep/                       # AEP test suite (66 tests at last count)
└── frontend/                            # Existing frontend — untouched by Phases 0–1
```

---

## Feature flags

Defined in `backend/app/aep/feature_flags.py`. All 16 flags below
default `false` except `human_approval_required` which defaults `true`
(safety).

| Flag                              | Phase | Effect when on                                                                |
|-----------------------------------|------:|-------------------------------------------------------------------------------|
| `autonomous_engine_enabled`       |     6 | Master switch. Without this on, every capability flag below is forced false. |
| `llm_gateway_enabled`             |     1 | `/LLM/*` routes proxy to Ollama instead of returning 503.                    |
| `webhook_receiver_enabled`        |     2 | `/api/v1/aep/webhooks/github` accepts GitHub events.                         |
| `github_actions_runtime_enabled`  |     3 | GHA Runtime Manager may generate workflow YAML and trigger runs.             |
| `agent_planner_enabled`           |     3 | Loads the Planner agent.                                                     |
| `agent_coder_enabled`             |     3 | Loads the Coder agent.                                                       |
| `agent_debugger_enabled`          |     5 | Loads the Debugger agent.                                                    |
| `agent_tester_enabled`            |     5 | Loads the Tester agent.                                                      |
| `agent_reviewer_enabled`          |     5 | Loads the Reviewer agent.                                                    |
| `agent_security_audit_enabled`    |     5 | Loads the Security Audit agent.                                              |
| `agent_documentation_enabled`     |     5 | Loads the Documentation agent.                                               |
| `agent_devops_enabled`            |     5 | Loads the DevOps agent.                                                      |
| `memory_system_enabled`           |     4 | Activates the memory store + Context Engine.                                 |
| `multi_agent_enabled`             |     5 | Activates the Coordinator and multi-agent orchestration.                     |
| `autonomous_ui_enabled`           |     5 | Mounts the AEP frontend module.                                              |
| `human_approval_required`         |     0 | Executions pause at `AWAITING_APPROVAL` before destructive ops. **Default true.** |

Resolution precedence (highest priority first):

1. Per-tenant DB row in `aep_feature_flags` (`tenant_id` set).
2. Global DB row in `aep_feature_flags` (`tenant_id IS NULL`).
3. Env var `AEP_FLAG_<UPPER_NAME>` (truthy: `1|true|yes|on|enabled`).
4. The `FlagSpec.default` value.

Toggle a flag via `PUT /api/v1/aep/flags/{name}` (admin-only — see
`_has_admin_role` in `admin.py`).

---

## Environment variables

| Variable                       | Default                       | Purpose |
|--------------------------------|-------------------------------|---------|
| `AEP_OLLAMA_BASE_URL`          | `http://ollama:11434`         | Upstream Ollama endpoint. Falls back to the existing `OLLAMA_URL` core setting when unset. |
| `OLLAMA_CLOUD_API_KEY`         | _(unset)_                     | Sent as `Authorization: Bearer <key>`. Set this when targeting Ollama Cloud. |
| `AEP_OLLAMA_API_KEY`           | _(unset)_                     | Alternate name for the same key. `OLLAMA_CLOUD_API_KEY` wins if both set. |
| `AEP_DEFAULT_MODEL`            | `gemma4:31b-cloud`            | Primary model name (spec §2.1). |
| `AEP_EMBEDDING_MODEL`          | `nomic-embed-text`            | Embedding model. |
| `AEP_OLLAMA_REQUEST_TIMEOUT`   | `120`                         | Upstream request timeout (seconds). |
| `AEP_OLLAMA_CONNECT_TIMEOUT`   | `10`                          | Upstream connect timeout (seconds). |
| `AEP_OLLAMA_MAX_RETRIES`       | `2`                           | Retries on transient network/5xx failures. |
| `AEP_OLLAMA_BACKOFF_INITIAL`   | `0.5`                         | Initial exponential backoff delay (seconds). |
| `AEP_OLLAMA_BACKOFF_MAX`       | `8.0`                         | Maximum backoff delay (seconds). |
| `AEP_OLLAMA_USER_AGENT`        | `devbuddy-aep/1`              | User-Agent header attached to upstream calls. |
| `AEP_MODEL_FOR_<TASK_TYPE>`    | _(unset)_                     | Override the routing table for a specific task type, e.g. `AEP_MODEL_FOR_CODE=phi3:medium`. |
| `AEP_FLAG_<UPPER_NAME>`        | _(unset)_                     | Env-var override for a feature flag. Truthy values: `1\|true\|yes\|on\|enabled`. |

Existing (pre-AEP) settings that the AEP layer reads but never
modifies: `DATABASE_URL`, `OLLAMA_URL`, `SECRET_KEY`, `SUPABASE_*`,
`LOKI_URL`.

---

## Local development & verification

### Bootstrap

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres for tests (Docker is the easiest path):
docker run -d --name pg-aep \
  -e POSTGRES_USER=devbuddy -e POSTGRES_PASSWORD=devbuddy \
  -e POSTGRES_DB=devbuddy_test \
  -p 5432:5432 postgres:16-alpine

# Required env vars for the test suite:
export DATABASE_URL='postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy_test'
export SECRET_KEY='test-secret-key-32-chars-long!'
export SUPABASE_URL='https://test.supabase.co'
export SUPABASE_ANON_KEY='test-anon-key'
export SUPABASE_JWT_SECRET='test-jwt-secret-32-chars-long!!'
```

### Run the test suite

```bash
pytest tests/aep/ -q          # 79 tests at last count (56 AEP core + 23 router)
pytest tests/test_smoke.py -q # 10 pre-existing smoke tests
ruff check app/aep tests/aep --select E,F,W --ignore E501
mypy app/aep --ignore-missing-imports --no-strict-optional
```

The only mypy error remaining (`app/core/config.py:76 Missing named
argument "DATABASE_URL"`) is **pre-existing**, unrelated to AEP, and
acknowledged.

### Run the full stack

```bash
docker compose up -d                 # dev — backend + postgres + ollama + loki + grafana
docker compose -f docker-compose.prod.yml up -d   # prod — adds nginx + frontend
```

### Flip the Phase 1 gateway on

Pick one:

```bash
# Env var path (immediate, no DB needed):
export AEP_FLAG_LLM_GATEWAY_ENABLED=true
export AEP_FLAG_AUTONOMOUS_ENGINE_ENABLED=true   # master switch
```

```http
PUT /api/v1/aep/flags/autonomous_engine_enabled  {"enabled": true}
PUT /api/v1/aep/flags/llm_gateway_enabled        {"enabled": true}
```

Then probe:

```bash
curl http://localhost:8000/LLM/health
# expect: {"status":"ok","phase":"phase_1","upstream":{...},"default_model":"gemma4:31b-cloud", ...}
```

---

## Conventions & guardrails

**Code style.**
- Use `Mapped`, `mapped_column`, `UUID(as_uuid=True)` for all new
  models, matching `app/models/task.py`.
- All new async functions, no sync DB calls in request paths.
- Type-annotate every function signature; prefer `from __future__ import
  annotations` for forward references.
- Pydantic v2 models for every request/response. Reject `dict[str, Any]`
  in route signatures.
- Use `structlog` via `aep_logger("component.name")` for all AEP logs.
  Never use `print` or `logging.info` directly.

**Module boundaries.**
- AEP code lives under `backend/app/aep/`. Existing code lives
  elsewhere. **Cross only via the Compatibility Adapter.**
- Never import from `app.aep.*` in non-AEP code unless behind a feature
  flag check.
- The Phase 0 LLM gateway namespace is `/LLM` at the root, not
  `/api/v1/LLM`. This is required by spec §2.2.
- Admin endpoints live under `/api/v1/aep/*` and follow the existing
  versioning convention.

**Git.**
- One PR per phase (split larger phases — e.g. Phase 5 — into
  sub-PRs). Each PR rebases on `scaffold/initial-platform` (or the
  current integration branch).
- PR titles: `Phase N — <short description>`.
- Never push to `main` directly. Never amend or force-push someone
  else's commit. `--force-with-lease` is OK on your own feature
  branch after a rebase.
- Commit messages: imperative, present tense, body explains *why*, not
  *what*.

**Tests.**
- Owner directive (2026-05-26): the AEP layer test suite is paused.
  Phase 1 router has 23 tests; everything else relies on the existing
  56 AEP core + 10 smoke tests. New phases should **not** invest in
  unit tests until the owner re-opens that lane. Functional verification
  (manual probes, integration scripts, e2e smoke) is acceptable in the
  interim.

**Security.**
- Never log a secret value. Use the `aep_secrets_metadata` table for
  metadata only; ciphertext lives in the secret manager.
- All shell commands injected into a generated workflow YAML must
  pass through `CommandValidator` (Phase 6). Until then, generated
  workflow YAML must be reviewed by a human before being committed.
- Tenant isolation is the responsibility of every query against an
  `aep_*` table. Until Phase 6 lands RLS, all repository methods MUST
  accept and apply a `tenant_id` filter explicitly.

---

## Open decisions (need owner input)

These were surfaced in PR #2 and remain unanswered. An agent picking up
the work should ask the owner before making assumptions, or proceed with
the documented default and flag the choice in the PR description.

1. **Ollama Cloud auth header.** Current default:
   `Authorization: Bearer <key>`. Change if Ollama Cloud uses a
   different header (e.g. `X-API-Key`).
2. **`gemma4:31b-cloud` exact tag.** Confirm this matches the model
   name Ollama Cloud actually exposes. Alternatives discussed:
   `gpt-oss:120b-cloud`, `gemma2:27b-cloud`. Update
   `AepLlmConfig.default_model` and `SPEC_DEFAULT_MAPPING` if the tag
   differs.
3. **GCP database strategy** (Phase 4 forcing function).
   - (a) Keep container Postgres on the e2-micro VM.
   - (b) Cloud SQL for PostgreSQL (~$10/mo, pgvector available).
   - (c) AlloyDB (~$50+/mo).
   Decision needed before pgvector enablement.
4. **GCP Ollama runtime sizing.** Cloud mode (current default) avoids
   the need for a GPU VM. If the owner ever wants fully self-hosted
   inference, the e2-micro VM is insufficient — a GPU VM
   (`g2-standard-4` + L4 ≈ $500/mo, or `n1-standard-4` + T4 ≈ $250/mo)
   would be required.
5. **GitHub App vs PAT for Phase 2.** Spec strongly prefers GitHub
   App. Confirm the owner wants to register a GitHub App before
   Phase 2 work begins, and provide the App ID / private key.
6. **Webhook secret rotation policy.** Per-repo or global secret in
   `aep_repositories`?

---

## Related documents

- [`EXTENSIONS.md`](./EXTENSIONS.md) — public contract: flags, hooks,
  routes, tables, AgentPlugin interface.
- [`DEPLOY_GCP.md`](./DEPLOY_GCP.md) — GCP deployment topology
  (devbuddy.org, e2-micro VM, persistent disk layout).
- [`README.md`](./README.md) — top-level project intro (pre-AEP).
- [`AGENT_GUIDE.md`](./AGENT_GUIDE.md) — pre-AEP agent docs (legacy,
  retained for reference; AEP supersedes once Phase 5 ships its UI).
- [`PRODUCTION.md`](./PRODUCTION.md) — pre-AEP production runbook.

The authoritative AEP spec is the 14-part *Autonomous AI Software
Engineering Platform — Implementation Specification* provided by the
project owner. This document tracks against that spec; when conflicts
arise, the spec wins.

---

_Last updated: 2026-05-26. Maintainer of record for Phases 0–1: Devin
(session [baea1b18](https://app.devin.ai/sessions/baea1b182d6f4222abda96cbf522ff14))._
