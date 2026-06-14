# AEP Hardening Report

> **Status:** Phase 6 implementation complete. This document records the
> security controls, isolation mechanisms, and observability features
> implemented, along with recommendations for load testing and
> penetration testing.

---

## 1. Secret Management

**Implementation:** `backend/app/aep/security/secrets.py`

| Control                       | Status |
|-------------------------------|--------|
| AES-256-GCM encryption at rest | Done   |
| Unified set/get/rotate/delete API | Done |
| Metadata-only in `aep_secrets_metadata` table | Done |
| Never log plaintext values    | Done   |
| Key rotation without downtime | Done (re-encrypts with new key) |
| Integration with GitHub Secrets for workflow injection | Done |

**Key derivation:** Uses `PBKDF2-HMAC-SHA256` with 100,000 iterations
from the `AEP_SECRET_ENCRYPTION_KEY` env var. A random 96-bit nonce is
generated per encryption operation.

**Recommendation:** Run a secrets-in-logs audit using `grep` across all
log output to verify no plaintext leakage. Consider adding automated
scanning (e.g., `trufflehog`, `gitleaks`) to CI.

---

## 2. Command Validation

**Implementation:** `backend/app/aep/security/command_validator.py`

| Control                       | Status |
|-------------------------------|--------|
| Blocklist of dangerous commands (rm -rf, mkfs, dd, etc.) | Done |
| Regex pattern matching for shell injection | Done |
| Audit logging of all validation results | Done |
| Fail-closed (rejected commands prevent execution) | Done |

**Blocklist categories:**
- Filesystem destruction: `rm -rf /`, `mkfs`, `fdisk`
- Privilege escalation: `sudo`, `su`, `chmod 777`
- Network exfiltration: `nc -l`, `curl | bash`, `wget -O- | sh`
- Credential access: `cat /etc/shadow`, `printenv | grep -i key`

**Recommendation:** Expand the blocklist based on real-world agent
outputs. Consider a whitelist-based approach for production deployments
where only approved commands pass validation.

---

## 3. RBAC (Role-Based Access Control)

**Implementation:** `backend/app/aep/security/rbac.py`

| Role            | Capabilities                                              |
|-----------------|-----------------------------------------------------------|
| `aep:viewer`    | Read executions, view plans, read logs                    |
| `aep:operator`  | All viewer + submit tasks, approve/reject plans           |
| `aep:admin`     | All operator + manage repos, toggle flags, manage secrets |
| `aep:system`    | All admin + internal state transitions, direct agent invocation |

**Enforcement:** Middleware checks JWT claims against required role for
each endpoint. Integrates with existing JWT auth via the Compatibility
Adapter.

**Recommendation:** Add integration tests that verify each endpoint
rejects requests from insufficient roles. Document the role assignment
workflow for new team members.

---

## 4. Tenant Isolation

**Implementation:** `backend/app/aep/security/tenant_isolation.py`

| Control                       | Status |
|-------------------------------|--------|
| SQLAlchemy event listener (query-time assertion) | Done |
| Postgres Row-Level Security (RLS) policies on all `aep_*` tables | Done |
| Redis key namespacing under `aep:{tenant_id}:` | Done |
| Migration 006 applies RLS policies | Done |

**RLS policy pattern:**
```sql
CREATE POLICY tenant_isolation_select ON aep_executions
  FOR SELECT USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

**SQLAlchemy listener:** Fires on `before_execute` for `SELECT`,
`INSERT`, `UPDATE`, `DELETE` on any `aep_*` table. Asserts that a
`tenant_id` filter is present in the WHERE clause. Raises
`TenantIsolationViolation` if missing.

**Recommendation:** Run a full query audit in staging to verify no
cross-tenant data leakage. Test with two tenants simultaneously making
requests and verify strict isolation.

---

## 5. Observability

**Implementation:** `backend/app/aep/observability_ext/`

| Component       | Technology      | Status |
|-----------------|-----------------|--------|
| Metrics         | Prometheus (Counter, Histogram, Gauge) | Done |
| Structured logging | structlog → Loki | Done |
| Distributed tracing | OpenTelemetry (W3C traceparent) | Done |
| Health endpoint | `GET /api/v1/aep/status` | Done |

**Key metrics exposed:**
- `aep_executions_total` (counter, by state)
- `aep_agent_invocations_total` (counter, by agent_name)
- `aep_llm_latency_seconds` (histogram)
- `aep_llm_tokens_total` (counter, input/output)
- `aep_active_executions` (gauge)

**Trace propagation path:**
```
HTTP Request → API Router → ExecutionService → Agent Plugin → LLM Gateway → Ollama
     ↕              ↕              ↕               ↕              ↕
  [span]        [span]         [span]          [span]        [span]
```

**Recommendation:** Set up Grafana dashboards for the metrics above.
Configure alerting for `aep_llm_latency_seconds` P99 > 30s and
`aep_active_executions` > 50.

---

## 6. Load Testing Plan

### Objectives

- Verify system stability under sustained load
- Identify bottlenecks in the LLM gateway and agent pipeline
- Validate connection pool sizing (PostgreSQL, Redis)
- Measure latency percentiles under concurrent execution

### Proposed test scenarios

| Scenario                  | Concurrent users | Duration | Target |
|---------------------------|-----------------|----------|--------|
| Baseline                  | 1               | 5 min    | Establish P50/P99 latency |
| Light load                | 10              | 10 min   | < 2s P99 for API endpoints |
| Moderate load             | 50              | 15 min   | No 5xx errors |
| Stress test               | 100+            | 30 min   | Graceful degradation |
| Spike                     | 0 → 100 → 0    | 5 min    | Recovery within 30s |

### Tool recommendation

Use **Locust** (Python-based, integrates well with the existing test
infrastructure):

```python
from locust import HttpUser, task, between

class AepUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def list_executions(self):
        self.client.get("/api/v1/aep/executions")

    @task(1)
    def submit_task(self):
        self.client.post("/api/v1/aep/executions", json={
            "title": "Load test task",
            "description": "Generate a simple function",
        })
```

### Resource monitoring during load tests

- PostgreSQL: connection count, query latency, WAL lag
- Redis: memory usage, connected clients, ops/sec
- Ollama: GPU utilization, queue depth, inference latency
- Backend: CPU, memory, open file descriptors, event loop lag

---

## 7. Security Audit Checklist

| # | Check                                      | Status  | Notes |
|---|---------------------------------------------|---------|-------|
| 1 | No secrets in source control               | Pass    | `.env` in `.gitignore`, no hardcoded tokens |
| 2 | All AEP endpoints require authentication   | Pass    | `get_current_user` dependency on all routes |
| 3 | HMAC webhook verification                   | Pass    | Constant-time comparison via `hmac.compare_digest` |
| 4 | SQL injection prevention                    | Pass    | SQLAlchemy parameterized queries throughout |
| 5 | XSS prevention (frontend)                  | Pass    | React auto-escapes, no `dangerouslySetInnerHTML` |
| 6 | CSRF protection                            | Pass    | Token-based auth (no cookies for API) |
| 7 | Rate limiting on LLM gateway               | Partial | Relies on upstream Ollama rate limits |
| 8 | Input validation                           | Pass    | Pydantic models on all request bodies |
| 9 | Error messages don't leak internals        | Pass    | Generic HTTP errors, details in server logs only |
| 10 | Dependency vulnerability scan              | Pending | Run `pip-audit` and `npm audit` |
| 11 | Container security (non-root)             | Pending | Verify Dockerfile uses non-root user |
| 12 | Network segmentation                      | Pass    | Ollama on internal Docker network only |

---

## 8. Remediation Items

| Priority | Item                                       | Effort |
|----------|--------------------------------------------|--------|
| High     | Add application-level rate limiting (e.g., `slowapi`) to LLM endpoints | 2h |
| High     | Run `pip-audit` + `npm audit` and fix critical CVEs | 1h |
| Medium   | Verify Dockerfiles run as non-root user    | 30min |
| Medium   | Add CSP headers to frontend Nginx/Caddy config | 1h |
| Low      | Implement request size limits on webhook endpoint | 30min |
| Low      | Add automated secrets scanning to CI (gitleaks) | 1h |

---

## 9. Conclusion

The Phase 6 hardening layer provides defense-in-depth:

1. **Encryption at rest** for all AEP-managed secrets
2. **Command validation** prevents agents from executing dangerous operations
3. **RBAC** enforces least-privilege access to AEP capabilities
4. **Tenant isolation** at both application and database level
5. **Full observability** stack for monitoring, debugging, and alerting

The system is ready for staging deployment with the caveat that load
testing and the remediation items above should be completed before
production traffic is routed to the AEP layer.
