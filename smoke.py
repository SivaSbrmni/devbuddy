"""
DevBuddy local smoke check — runs against http://localhost:8000
Exercises: health -> dev-token -> /me -> create task -> list tasks -> state transition -> audit log
No pytest required, just: python smoke.py
"""
import sys
import json
import urllib.request
import urllib.error
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

BASE = "http://localhost:8000"
GREEN = "\033[92m"
RED   = "\033[91m"
BOLD  = "\033[1m"
RESET = "\033[0m"

token = None


def req(method, path, body=None, auth=True):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(label, status, body, expect_status=200):
    ok = status == expect_status
    icon = f"{GREEN}[OK]{RESET}" if ok else f"{RED}[FAIL]{RESET}"
    print(f"  {icon}  {BOLD}{label}{RESET}  ->  HTTP {status}")
    if not ok:
        print(f"       {RED}{body}{RESET}")
        sys.exit(1)
    return body


print(f"\n{BOLD}=== DevBuddy Local Smoke Check ==={RESET}\n")

# 1. Health
s, b = req("GET", "/health", auth=False)
check("GET  /health", s, b)

# 2. Dev token
s, b = req("POST", "/api/v1/auth/dev-token",
           {"email": "smoke@devbuddy.local", "name": "Smoke User"}, auth=False)
r = check("POST /api/v1/auth/dev-token", s, b, 200)
token = r["access_token"]
print(f"       token: {token[:40]}…")

# 3. /me — verifies JWT round-trip through backend
s, b = req("GET", "/api/v1/auth/me")
r = check("GET  /api/v1/auth/me", s, b)
print(f"       user: {r}")

# 4. Create task
s, b = req("POST", "/api/v1/tasks", {
    "title": "Smoke test task",
    "description": "Automated smoke check",
    "policy_profile": "standard",
    "metadata": {"source": "smoke"}
})
r = check("POST /api/v1/tasks", s, b, 200)
task_id = r["id"]
print(f"       task_id: {task_id}  state: {r['state']}")

# 5. Get task by ID
s, b = req("GET", f"/api/v1/tasks/{task_id}")
r = check("GET  /api/v1/tasks/:id", s, b)
print(f"       state: {r['state']}  events: {len(r['events'])}")

# 6. List tasks
s, b = req("GET", "/api/v1/tasks")
r = check("GET  /api/v1/tasks", s, b)
print(f"       total tasks visible: {len(r)}")

# 7. State transition PENDING → PLANNING
s, b = req("PATCH", f"/api/v1/tasks/{task_id}/state",
           {"to_state": "PLANNING", "reason": "smoke test"})
r = check("PATCH /api/v1/tasks/:id/state  (PENDING->PLANNING)", s, b)
print(f"       new state: {r['state']}")

# 8. State transition PLANNING → EXECUTING
s, b = req("PATCH", f"/api/v1/tasks/{task_id}/state",
           {"to_state": "EXECUTING", "reason": "smoke test"})
r = check("PATCH /api/v1/tasks/:id/state  (PLANNING->EXECUTING)", s, b)
print(f"       new state: {r['state']}")

# 9. Get task again — confirm events recorded
s, b = req("GET", f"/api/v1/tasks/{task_id}")
r = check("GET  /api/v1/tasks/:id (events check)", s, b)
print(f"       events recorded: {len(r['events'])}")
for ev in r["events"]:
    print(f"         {ev['event_type']:25s}  {str(ev.get('from_state','none')):20s} -> {ev.get('to_state','none')}")

# 10. Audit log
s, b = req("GET", "/api/v1/audit?limit=10")
r = check("GET  /api/v1/audit", s, b)
print(f"       audit entries: {len(r)}")

print(f"\n{GREEN}{BOLD}All checks passed [OK]{RESET}\n")
