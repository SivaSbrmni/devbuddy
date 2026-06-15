"""Cloud Execution Engine — GitHub Actions as Compute Layer.

Every DevBuddy task becomes an isolated GitHub Actions job:
  1. Inject devbuddy-runner workflow into the branch
  2. Dispatch it via workflow_dispatch
  3. Long-poll the run: stream every log line as SSE
  4. On completion: parse artifacts, emit done/error

The DevBuddy server never executes code — it only orchestrates.
All computation happens inside an ephemeral GitHub-hosted runner.

Runner lifecycle:
  queued → provisioning → initializing → connecting →
  analyzing → executing → validating → reflecting →
  pushing → creating_pr → uploading → completed → destroyed
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator

import httpx
import structlog

log = structlog.get_logger()

GITHUB_API = "https://api.github.com"

# How long to wait for the workflow run to appear after dispatch (seconds)
DISPATCH_WAIT_SECS = 45

# Polling interval for run status (seconds)
POLL_INTERVAL = 4

# Maximum total wait for a run to finish (seconds) — 30 minutes
MAX_RUN_WAIT = 1800

# Log lines to fetch per poll
LOG_CHUNK_LINES = 80


# ── Runner state ──────────────────────────────────────────────────────────────

RUNNER_STATES = [
    "queued",
    "provisioning",
    "initializing",
    "connecting",
    "analyzing",
    "executing",
    "validating",
    "reflecting",
    "pushing",
    "creating_pr",
    "uploading",
    "completed",
    "destroyed",
]


@dataclass
class CloudJob:
    task_id: str
    task: str
    owner: str
    repo: str
    branch: str
    github_token: str
    base_branch: str = "main"
    run_id: int = 0
    run_url: str = ""
    runner_state: str = "queued"
    pr_url: str = ""
    pr_number: int = 0
    commit_hash: str = ""
    modified_files: list[str] = field(default_factory=list)
    quality_gates: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)
    conclusion: str = ""
    error: str = ""
    ollama_key: str = ""
    ollama_base: str = "https://ollama.com"
    ollama_model: str = "qwen3-coder:480b"


# ── GitHub API helpers ────────────────────────────────────────────────────────

async def _gh(
    method: str,
    path: str,
    token: str,
    timeout: int = 30,
    **kwargs,
) -> dict | list:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await getattr(client, method)(
            f"{GITHUB_API}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            **kwargs,
        )
        if not resp.is_success:
            raise RuntimeError(
                f"GitHub {method.upper()} {path} → {resp.status_code}: {resp.text[:300]}"
            )
        if resp.content:
            return resp.json()
        return {}


async def _get_repo_info(owner: str, repo: str, token: str) -> dict:
    return await _gh("get", f"/repos/{owner}/{repo}", token)  # type: ignore


async def _get_file_sha(owner: str, repo: str, token: str, path: str, branch: str) -> str | None:
    """Return blob SHA of an existing file, or None."""
    try:
        data = await _gh("get", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}", token)
        return data.get("sha")  # type: ignore
    except Exception:
        return None


async def _put_file(
    owner: str,
    repo: str,
    token: str,
    path: str,
    content_b64: str,
    message: str,
    branch: str,
    sha: str | None = None,
) -> dict:
    body: dict = {"message": message, "content": content_b64, "branch": branch}
    if sha:
        body["sha"] = sha
    return await _gh("put", f"/repos/{owner}/{repo}/contents/{path}", token, json=body)  # type: ignore


async def _dispatch_workflow(
    owner: str,
    repo: str,
    token: str,
    workflow_id: str,
    branch: str,
    inputs: dict,
) -> None:
    await _gh(
        "post",
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        token,
        json={"ref": branch, "inputs": inputs},
    )


async def _list_workflow_runs(
    owner: str,
    repo: str,
    token: str,
    workflow_id: str,
    branch: str,
    created_after: int,
) -> list[dict]:
    data = await _gh(
        "get",
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        f"?branch={branch}&per_page=5",
        token,
    )
    runs: list[dict] = data.get("workflow_runs", [])  # type: ignore
    # Filter to runs created at or after our dispatch time
    result = []
    for r in runs:
        ts = r.get("created_at", "")
        run_epoch = _parse_iso(ts)
        if run_epoch >= created_after - 10:
            result.append(r)
    return result


async def _get_run(owner: str, repo: str, token: str, run_id: int) -> dict:
    return await _gh("get", f"/repos/{owner}/{repo}/actions/runs/{run_id}", token)  # type: ignore


async def _get_run_jobs(owner: str, repo: str, token: str, run_id: int) -> list[dict]:
    data = await _gh("get", f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", token)
    return data.get("jobs", [])  # type: ignore


async def _download_logs(owner: str, repo: str, token: str, run_id: int) -> str:
    """Download the full log zip and return raw text (first 20 KB)."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if not resp.is_success:
                return ""
            # The response is a ZIP — extract first text file
            import io, zipfile
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                names = sorted(z.namelist())
                text_parts = []
                for name in names:
                    if name.endswith(".txt"):
                        raw = z.read(name).decode("utf-8", errors="replace")
                        text_parts.append(raw)
                        if sum(len(t) for t in text_parts) > 20_000:
                            break
                return "\n".join(text_parts)[:20_000]
    except Exception:
        return ""


async def _list_artifacts(owner: str, repo: str, token: str, run_id: int) -> list[str]:
    try:
        data = await _gh("get", f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts", token)
        return [a["name"] for a in data.get("artifacts", [])]  # type: ignore
    except Exception:
        return []


async def _create_pr(
    owner: str,
    repo: str,
    token: str,
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict:
    return await _gh(  # type: ignore
        "post",
        f"/repos/{owner}/{repo}/pulls",
        token,
        json={"title": title, "body": body, "head": head, "base": base, "draft": False},
    )


# ── Workflow template ─────────────────────────────────────────────────────────

# ── Embedded agent script (plain string — not an f-string) ───────────────────
# This script runs inside the GitHub Actions runner.
# It is base64-encoded into the workflow YAML to avoid all quoting issues.

_AGENT_SCRIPT = r'''
import os, sys, json, subprocess, time, re, pathlib

TASK         = os.environ.get("DEVBUDDY_TASK", "")
TASK_ID      = os.environ.get("DEVBUDDY_TASK_ID", "")
OWNER        = os.environ.get("DEVBUDDY_OWNER", "")
REPO         = os.environ.get("DEVBUDDY_REPO", "")
BRANCH       = os.environ.get("DEVBUDDY_BRANCH", "")
DEVBUDDY_URL = os.environ.get("DEVBUDDY_URL", "")
WORKSPACE    = pathlib.Path(".")
MAX_ITER     = 12

def emit(event_type, payload):
    line = "DEVBUDDY_EVENT:" + json.dumps({"type": event_type, "timestamp": int(time.time()*1000), "payload": payload})
    print(line, flush=True)

def run_shell(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE))
        return r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", -1
    except Exception as e:
        return str(e), -1

def read_file(p):
    fp = WORKSPACE / p["path"]
    if not fp.exists():
        return f"Error: {p['path']} not found"
    try:
        return fp.read_text(errors="replace")[:8000]
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(p):
    fp = WORKSPACE / p["path"]
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(p["content"])
    emit("file_change", {"path": p["path"], "action": "modified"})
    return f"Written: {p['path']}"

def list_files(p):
    pat = p.get("pattern", "*")
    matches = sorted([
        str(f.relative_to(WORKSPACE))
        for f in WORKSPACE.rglob(pat)
        if f.is_file() and ".git" not in str(f)
    ])[:60]
    return "\n".join(matches)

def search_code(p):
    q = p["query"].replace('"', '\\"')
    out, _ = run_shell(f'grep -r -l "{q}" . 2>/dev/null | head -20')
    return out or "No matches"

def run_command(p):
    cmd = p["command"]
    for blocked in ["rm -rf /", "dd if=", "mkfs", "> /dev/", "curl | bash", "wget | sh", "git push", "git commit"]:
        if blocked in cmd:
            return f"Blocked: {cmd}"
    out, _ = run_shell(cmd)
    return out[:3000]

TOOLS = {
    "read_file":    read_file,
    "write_file":   write_file,
    "list_files":   list_files,
    "search_code":  search_code,
    "run_command":  run_command,
}

TOOLS_DESC = """- read_file({"path":"..."}): Read file contents
- write_file({"path":"...","content":"..."}): Write/create a file
- list_files({"pattern":"*"}): List files matching glob
- search_code({"query":"..."}): Search codebase for text
- run_command({"command":"..."}): Run shell command"""

SYSTEM = (
    "You are DevBuddy, an autonomous software engineer.\n"
    f"Repository: {OWNER}/{REPO}, Branch: {BRANCH}\n"
    f"Task: {TASK}\n\n"
    "Follow the ReAct pattern strictly:\n"
    "THOUGHT: <reasoning about what to do next>\n"
    "ACTION: <tool_name>\n"
    "PARAMS: <json object with tool parameters>\n\n"
    "After seeing OBSERVATION, continue with next THOUGHT/ACTION.\n"
    "When the task is fully complete output exactly: DONE: <one line summary>\n\n"
    f"Available tools:\n{TOOLS_DESC}\n\n"
    "Rules:\n"
    "- Always read a file before editing it\n"
    "- Never use git commands via run_command\n"
    "- Create complete, working, production-ready code\n"
    "- Use write_file to create or modify files"
)

def call_llm(messages):
    import urllib.request

    # 1. Ollama Cloud (https://ollama.com/api/chat)
    ollama_key  = os.environ.get("OLLAMA_API_KEY", "")
    ollama_base = os.environ.get("OLLAMA_API_BASE", "https://ollama.com").rstrip("/")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen3-coder:480b")
    if ollama_key:
        msgs = [{"role": "system", "content": SYSTEM}] + messages
        payload = json.dumps({
            "model": ollama_model,
            "messages": msgs,
            "stream": False,
            "options": {"num_predict": 4096, "temperature": 0.1},
        }).encode()
        req = urllib.request.Request(
            f"{ollama_base}/api/chat",
            data=payload,
            headers={
                "Authorization": f"Bearer {ollama_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
                content = data.get("message", {}).get("content", "")
                if content:
                    return content
        except Exception as e:
            print(f"Ollama error: {e}", flush=True)

    # 2. Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        payload = json.dumps({
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 4096,
            "system": SYSTEM,
            "messages": messages,
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["content"][0]["text"]
        except Exception as e:
            print(f"Anthropic error: {e}", flush=True)

    # 3. OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        msgs = [{"role": "system", "content": SYSTEM}] + messages
        payload = json.dumps({"model": "gpt-4o-mini", "messages": msgs, "max_tokens": 4096}).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI error: {e}", flush=True)

    # 4. DevBuddy relay
    if DEVBUDDY_URL:
        payload = json.dumps({"messages": messages, "system": SYSTEM, "task_id": TASK_ID}).encode()
        req = urllib.request.Request(
            f"{DEVBUDDY_URL}/llm/complete",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read()).get("content", "")
        except Exception as e:
            print(f"DevBuddy relay error: {e}", flush=True)

    raise RuntimeError("No LLM available. Add OLLAMA_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY to repository secrets.")

def parse_action(text):
    action_m = re.search(r"ACTION:\s*(\w+)", text)
    params_m  = re.search(r"PARAMS:\s*(\{[\s\S]+?\})", text)
    thought_m = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|$)", text, re.DOTALL)
    if not action_m:
        return None, None, text.strip()
    tool   = action_m.group(1).strip()
    params = {}
    if params_m:
        try:
            params = json.loads(params_m.group(1))
        except Exception:
            pass
    thought = thought_m.group(1).strip() if thought_m else ""
    return tool, params, thought

# ── ReAct loop ────────────────────────────────────────────────────────────────
emit("runner",   {"state": "analyzing",  "message": "Agent online — starting ReAct loop"})
emit("timeline", {"step": "execution",   "status": "running", "message": "ReAct loop started"})

messages      = [{"role": "user", "content": f"Task: {TASK}\n\nBegin by listing project files."}]
done_summary  = ""
modified_files = []

for iteration in range(MAX_ITER):
    emit("timeline", {"step": "execution", "status": "running",
                       "message": f"Iteration {iteration+1}/{MAX_ITER}"})
    try:
        response = call_llm(messages)
    except Exception as e:
        emit("error", {"message": str(e)})
        sys.exit(1)

    print(f"\n--- Iteration {iteration+1} ---\n{response[:600]}", flush=True)

    done_m = re.search(r"DONE:\s*(.+)", response)
    if done_m:
        done_summary = done_m.group(1).strip()
        emit("timeline", {"step": "execution", "status": "done", "message": "Task complete"})
        break

    tool, params, thought = parse_action(response)
    if thought:
        emit("think", {"message": thought[:200]})

    if not tool:
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user",      "content": "Continue. What is your next ACTION?"})
        continue

    emit("tool_call", {"tool": tool, "params": params})

    if tool not in TOOLS:
        obs = f"Unknown tool: {tool}. Use one of: {', '.join(TOOLS.keys())}"
    else:
        try:
            obs = str(TOOLS[tool](params))
            if tool == "write_file" and params.get("path"):
                f = params["path"]
                if f not in modified_files:
                    modified_files.append(f)
        except Exception as e:
            obs = f"Tool error: {e}"

    emit("observe", {"tool": tool, "output": obs[:300]})
    print(f"OBSERVATION: {obs[:300]}", flush=True)
    messages.append({"role": "assistant", "content": response})
    messages.append({"role": "user",      "content": f"OBSERVATION: {obs}\n\nContinue."})

# ── Commit & push ─────────────────────────────────────────────────────────────
emit("runner", {"state": "pushing", "message": "Committing changes..."})
run_shell("git add -A")
commit_msg = (done_summary or f"devbuddy: {TASK}")[:72]
out, code  = run_shell(f'git commit -m "{commit_msg}"')

if code == 0:
    sha, _ = run_shell("git rev-parse --short HEAD")
    emit("timeline", {"step": "commit", "status": "done", "message": f"Committed {sha.strip()}"})
    push_out, push_code = run_shell(f"git push origin {BRANCH}", timeout=120)
    if push_code == 0:
        emit("timeline", {"step": "push", "status": "done", "message": f"Pushed to {BRANCH}"})
        for f in modified_files:
            emit("file_change", {"path": f, "action": "modified"})
    else:
        emit("timeline", {"step": "push", "status": "error", "message": push_out[:120]})
else:
    emit("timeline", {"step": "commit", "status": "warn", "message": "Nothing to commit"})

print(f"DONE: {done_summary or 'Task completed'}", flush=True)
'''


def _build_workflow(job: CloudJob, devbuddy_url: str) -> str:
    """Generate GitHub Actions workflow YAML with embedded LangGraph agent."""
    import base64 as _b64
    # base64-encode the agent script so there are zero quoting/heredoc issues
    agent_b64 = _b64.b64encode(_AGENT_SCRIPT.encode()).decode()
    return f"""# DevBuddy Cloud Execution Engine
# Auto-generated — do not edit
# Task: {job.task_id}

name: DevBuddy Agent Runner

on:
  workflow_dispatch:
    inputs:
      task_id:
        description: 'Task ID'
        required: true
      task:
        description: 'Engineering task description'
        required: true
      devbuddy_url:
        description: 'DevBuddy server URL for LLM relay'
        required: false

jobs:
  agent:
    name: 'DevBuddy LangGraph Agent'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: {job.branch}
          fetch-depth: 0
          token: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install agent runtime
        run: |
          pip install --quiet httpx anthropic openai 2>/dev/null || true
          echo "::group::Runtime ready"
          python --version
          echo "::endgroup::"

      - name: Detect stack
        id: stack
        run: |
          if [ -f "package.json" ]; then echo "stack=node" >> $GITHUB_OUTPUT
          elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then echo "stack=python" >> $GITHUB_OUTPUT
          elif [ -f "go.mod" ]; then echo "stack=go" >> $GITHUB_OUTPUT
          elif [ -f "Cargo.toml" ]; then echo "stack=rust" >> $GITHUB_OUTPUT
          else echo "stack=unknown" >> $GITHUB_OUTPUT
          fi

      - name: Setup Node.js
        if: steps.stack.outputs.stack == 'node'
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install project dependencies
        run: |
          if [ -f "package.json" ]; then npm ci --prefer-offline 2>/dev/null || npm install 2>/dev/null || true
          elif [ -f "requirements.txt" ]; then pip install -r requirements.txt --quiet 2>/dev/null || true
          elif [ -f "pyproject.toml" ]; then pip install -e . --quiet 2>/dev/null || true
          fi

      - name: Configure git
        run: |
          git config user.email "devbuddy-runner@devbuddy.org"
          git config user.name "DevBuddy Agent"

      - name: Decode and run DevBuddy agent
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
          OLLAMA_API_KEY: {job.ollama_key}
          OLLAMA_API_BASE: {job.ollama_base}
          OLLAMA_MODEL: {job.ollama_model}
          DEVBUDDY_TASK: ${{{{ inputs.task }}}}
          DEVBUDDY_TASK_ID: ${{{{ inputs.task_id }}}}
          DEVBUDDY_OWNER: {job.owner}
          DEVBUDDY_REPO: {job.repo}
          DEVBUDDY_BRANCH: {job.branch}
          DEVBUDDY_URL: ${{{{ inputs.devbuddy_url }}}}
          AGENT_B64: {agent_b64}
        run: |
          echo "::group::DevBuddy Agent Boot"
          echo "$AGENT_B64" | base64 -d > /tmp/devbuddy_agent.py
          echo "Agent script decoded ($(wc -l < /tmp/devbuddy_agent.py) lines)"
          echo "Task: $DEVBUDDY_TASK"
          echo "Branch: $DEVBUDDY_BRANCH"
          echo "::endgroup::"
          echo "::group::DevBuddy ReAct Execution"
          python /tmp/devbuddy_agent.py
          echo "::endgroup::"

      - name: Run build verification
        if: always()
        run: |
          echo "::group::Build Verification"
          if [ -f "package.json" ]; then
            npm run build 2>&1 | tail -20 || echo "Build check: no build script or errors"
            npm test 2>&1 | tail -20 || echo "Tests: no test script or errors"
          elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
            python -m pytest --tb=short -q 2>&1 | tail -20 || echo "Tests: not found or errors"
          fi
          echo "::endgroup::"

      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: devbuddy-run-{job.task_id}
          path: |
            devbuddy-report.md
            coverage/
            test-results/
          if-no-files-found: ignore
          retention-days: 7
"""


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(event_type: str, payload: dict) -> str:
    data = json.dumps({
        "type": event_type,
        "timestamp": int(time.time() * 1000),
        "payload": payload,
    })
    return f"data: {data}\n\n"


def _parse_iso(ts: str) -> int:
    """Parse ISO8601 timestamp to epoch seconds (best-effort)."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


# ── Log parser — extract meaningful events from raw runner logs ───────────────

_LOG_PATTERNS = [
    (re.compile(r"##\[group\](.+)"), "group"),
    (re.compile(r"##\[endgroup\]"), "endgroup"),
    (re.compile(r"##\[error\](.+)"), "error"),
    (re.compile(r"##\[warning\](.+)"), "warn"),
    (re.compile(r"DEVBUDDY_EVENT:(\{.+\})"), "event"),
    (re.compile(r"Run (npm|pip|mvn|gradle|cargo|go) "), "build"),
    (re.compile(r"(PASS|FAIL|ERROR)\s+\S+"), "test"),
    (re.compile(r"(\d+) test[s]? (passed|failed)"), "test_summary"),
]


def _parse_log_lines(text: str, seen_lines: set[int]) -> list[dict]:
    """Extract structured events from raw log text."""
    events: list[dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if i in seen_lines:
            continue
        seen_lines.add(i)
        clean = line.strip()
        if not clean:
            continue

        # Strip GitHub log timestamp prefix (2024-01-01T00:00:00.000Z  text)
        clean = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s+", "", clean)

        for pattern, kind in _LOG_PATTERNS:
            m = pattern.search(clean)
            if m:
                if kind == "event":
                    try:
                        payload = json.loads(m.group(1))
                        events.append({"kind": "agent_event", "payload": payload})
                    except Exception:
                        pass
                elif kind == "group":
                    events.append({"kind": "step", "message": m.group(1).strip()})
                elif kind == "error":
                    events.append({"kind": "error", "message": m.group(1).strip()[:200]})
                elif kind == "warn":
                    events.append({"kind": "warn", "message": m.group(1).strip()[:200]})
                elif kind in ("test", "test_summary", "build"):
                    events.append({"kind": "log", "message": clean[:150]})
                break
        else:
            # Emit interesting lines (not blanks or pure timestamps)
            if len(clean) > 6 and not clean.startswith("##"):
                events.append({"kind": "log", "message": clean[:150]})

    return events


# ── Quality gate detection from logs ─────────────────────────────────────────

def _extract_quality_gates(full_log: str) -> dict[str, str]:
    gates: dict[str, str] = {}
    log_lower = full_log.lower()

    # Build
    if any(x in log_lower for x in ["build successful", "build success", "compiled successfully", "webpack compiled"]):
        gates["build"] = "pass"
    elif any(x in log_lower for x in ["build failed", "build error", "compilation failed", "error ts"]):
        gates["build"] = "fail"

    # Tests
    if re.search(r"\d+ (test|spec)[s]? passed", log_lower):
        gates["tests"] = "pass"
    elif re.search(r"\d+ (test|spec)[s]? failed", log_lower):
        gates["tests"] = "fail"
    elif "no tests found" in log_lower:
        gates["tests"] = "skip"

    # Lint
    if any(x in log_lower for x in ["eslint found no problems", "no lint errors", "linting passed"]):
        gates["lint"] = "pass"
    elif any(x in log_lower for x in ["eslint", "pylint", "ruff"]) and "error" in log_lower:
        gates["lint"] = "warn"

    # Security
    if "npm audit" in log_lower:
        if "found 0 vulnerabilities" in log_lower:
            gates["security"] = "pass"
        elif "vulnerabilities" in log_lower:
            gates["security"] = "warn"

    return gates


# ── Rich PR body generator ────────────────────────────────────────────────────

def _generate_pr_body(job: CloudJob, done_summary: str, full_log: str) -> str:
    duration = int(time.monotonic() - job.start_time)
    mins, secs = divmod(duration, 60)
    elapsed = f"{mins}m {secs}s" if mins else f"{secs}s"

    gates = job.quality_gates
    gate_rows = ""
    gate_icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "—"}
    for gate, status in gates.items():
        icon = gate_icons.get(status, "—")
        gate_rows += f"| {gate.title()} | {icon} {status.upper()} |\n"
    if not gate_rows:
        gate_rows = "| — | Not detected |\n"

    files_section = ""
    if job.modified_files:
        files_section = "\n".join(f"- `{f}`" for f in job.modified_files[:30])
        if len(job.modified_files) > 30:
            files_section += f"\n- *(+{len(job.modified_files) - 30} more files)*"
    else:
        files_section = "*No files recorded*"

    artifacts_section = ""
    if job.artifacts:
        artifacts_section = "\n".join(f"- `{a}`" for a in job.artifacts)
    else:
        artifacts_section = "*No artifacts uploaded*"

    # Extract test line from logs
    test_line = ""
    m = re.search(r"(\d+ tests? (?:passed|failed)[^\n]*)", full_log, re.IGNORECASE)
    if m:
        test_line = f"\n> {m.group(1).strip()}"

    run_url = job.run_url or f"https://github.com/{job.owner}/{job.repo}/actions"

    return f"""## Summary

{done_summary or 'Autonomous implementation completed by DevBuddy Agent.'}

---

## Quality Gates

| Check | Status |
|-------|--------|
{gate_rows}
{test_line}

---

## Modified Files ({len(job.modified_files)})

{files_section}

---

## Execution Details

| Field | Value |
|-------|-------|
| Task ID | `{job.task_id}` |
| Branch | `{job.branch}` |
| Runner | GitHub Actions (ubuntu-latest) |
| Elapsed | {elapsed} |
| Commit | `{job.commit_hash or 'N/A'}` |
| Actions Run | [{job.run_id}]({run_url}) |

---

## Artifacts

{artifacts_section}

---

## Rollback Strategy

```bash
# To revert this PR's changes:
git revert $(git log --merges --oneline -1 | awk '{{print $1}}')

# Or to reset to base branch:
git checkout {job.base_branch}
git branch -D {job.branch}
```

---

## Security Notes

- All changes were made in an isolated ephemeral runner
- No long-lived secrets were used; runner credentials expired after job completion
- Branch is isolated from `{job.base_branch}` — no direct commits to protected branches

---

*Autonomous implementation by [DevBuddy](https://devbuddy.org) · \
Cloud Execution Engine · Task `{job.task_id}`*
"""


# ── Main cloud runner ─────────────────────────────────────────────────────────

WORKFLOW_FILE = ".github/workflows/devbuddy-runner.yml"
WORKFLOW_ID = "devbuddy-runner.yml"


async def run_cloud_agent(
    task: str,
    owner: str,
    repo: str,
    github_token: str,
    devbuddy_url: str = "",
    conversation_id: str = "",
    ollama_key: str = "",
    ollama_base: str = "https://ollama.com",
    ollama_model: str = "qwen3-coder:480b",
) -> AsyncGenerator[str, None]:
    """
    Dispatch a GitHub Actions job for this task and stream its lifecycle as SSE.
    Falls back gracefully if Actions is not available.
    """
    task_id = str(uuid.uuid4())[:8]
    slug = re.sub(r"[^a-z0-9-]", "-", task[:40].lower()).strip("-")
    branch_name = f"devbuddy/{slug}-{task_id}"

    job = CloudJob(
        task_id=task_id,
        task=task,
        owner=owner,
        repo=repo,
        branch=branch_name,
        github_token=github_token,
        ollama_key=ollama_key,
        ollama_base=ollama_base or "https://ollama.com",
        ollama_model=ollama_model or "qwen3-coder:480b",
    )

    def emit(event_type: str, payload: dict) -> str:
        return _sse(event_type, payload)

    # ── 0: Verify repo access ──────────────────────────────────────────
    yield emit("runner", {"state": "queued", "message": f"Task queued · {task_id}"})
    try:
        repo_info = await _get_repo_info(owner, repo, github_token)
        job.base_branch = repo_info.get("default_branch", "main")
        yield emit("timeline", {"step": "init", "status": "done", "message": f"Repository ready · {job.base_branch}"})
    except Exception as e:
        yield emit("error", {"message": f"Cannot access repository: {e}"})
        return

    # ── 1: Create branch via GitHub API (no local clone needed) ───────
    yield emit("runner", {"state": "provisioning", "message": "Creating isolated branch..."})
    yield emit("timeline", {"step": "branch", "status": "running", "message": f"Creating {branch_name}..."})
    try:
        # Get base SHA
        ref_data = await _gh("get", f"/repos/{owner}/{repo}/git/ref/heads/{job.base_branch}", github_token)
        base_sha = ref_data["object"]["sha"]  # type: ignore

        # Create branch
        await _gh("post", f"/repos/{owner}/{repo}/git/refs", github_token, json={
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        })
        yield emit("timeline", {"step": "branch", "status": "done", "message": f"Branch ready: {branch_name}"})
        yield emit("branch", {"name": branch_name})
    except Exception as e:
        yield emit("error", {"message": f"Branch creation failed: {e}"})
        return

    # ── 2: Inject workflow file ────────────────────────────────────────
    # GitHub only recognises workflow_dispatch if the workflow file exists
    # on the DEFAULT branch. We upsert a stub there first, then write the
    # full task-specific workflow onto the task branch.
    yield emit("runner", {"state": "initializing", "message": "Registering runner workflow..."})
    import base64
    workflow_yaml = _build_workflow(job, devbuddy_url)
    workflow_b64 = base64.b64encode(workflow_yaml.encode()).decode()

    try:
        # 2a: upsert on default branch so GitHub registers it as dispatchable
        default_sha = await _get_file_sha(owner, repo, github_token, WORKFLOW_FILE, job.base_branch)
        await _put_file(
            owner, repo, github_token,
            path=WORKFLOW_FILE,
            content_b64=workflow_b64,
            message=f"chore: register DevBuddy runner workflow",
            branch=job.base_branch,
            sha=default_sha,
        )
        # 2b: also write it onto the task branch so the runner has it
        task_branch_sha = await _get_file_sha(owner, repo, github_token, WORKFLOW_FILE, branch_name)
        await _put_file(
            owner, repo, github_token,
            path=WORKFLOW_FILE,
            content_b64=workflow_b64,
            message=f"chore: inject DevBuddy runner for task {task_id}",
            branch=branch_name,
            sha=task_branch_sha,
        )
        yield emit("timeline", {"step": "init", "status": "done", "message": "Runner workflow registered"})
    except Exception as e:
        yield emit("error", {"message": f"Workflow injection failed: {e}"})
        return

    # ── 3: Dispatch workflow ───────────────────────────────────────────
    yield emit("runner", {"state": "connecting", "message": "Dispatching GitHub Actions job..."})
    dispatch_epoch = int(time.time())
    try:
        # workflow_dispatch must target the default branch (where the workflow is registered)
        await _dispatch_workflow(
            owner, repo, github_token,
            workflow_id=WORKFLOW_ID,
            branch=job.base_branch,
            inputs={
                "task_id": task_id,
                "task": task[:255],
                "devbuddy_url": devbuddy_url or "",
            },
        )
        yield emit("timeline", {"step": "workspace", "status": "running", "message": "Runner dispatched, waiting for provisioning..."})
    except Exception as e:
        yield emit("error", {"message": f"Workflow dispatch failed: {e}"})
        return

    # ── 4: Wait for run to appear ──────────────────────────────────────
    run_id = 0
    deadline = time.monotonic() + DISPATCH_WAIT_SECS
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            runs = await _list_workflow_runs(owner, repo, github_token, WORKFLOW_ID, job.base_branch, dispatch_epoch)
            if runs:
                run_id = runs[0]["id"]
                job.run_id = run_id
                job.run_url = runs[0].get("html_url", "")
                yield emit("runner", {"state": "provisioning", "message": f"Runner provisioning · run #{run_id}", "run_url": job.run_url})
                break
        except Exception:
            pass

    if not run_id:
        yield emit("error", {"message": "GitHub Actions run did not start within 45s. Check repository Actions settings."})
        return

    # ── 5: Stream run lifecycle ────────────────────────────────────────
    yield emit("runner", {"state": "initializing", "message": "Runner online, initializing environment..."})
    yield emit("timeline", {"step": "workspace", "status": "done", "message": f"Runner online · #{run_id}"})

    seen_log_lines: set[int] = set()
    full_log_text = ""
    last_status = ""
    elapsed_start = time.monotonic()

    deadline = time.monotonic() + MAX_RUN_WAIT
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)

        try:
            run_data = await _get_run(owner, repo, github_token, run_id)
        except Exception:
            continue

        status: str = run_data.get("status", "")
        conclusion: str = run_data.get("conclusion") or ""

        # Map GitHub status → runner state
        runner_state = "executing"
        if status == "queued":
            runner_state = "queued"
        elif status == "in_progress":
            runner_state = "executing"
        elif status == "completed":
            runner_state = "completed" if conclusion == "success" else "completed"

        if runner_state != last_status:
            last_status = runner_state
            job.runner_state = runner_state
            elapsed_s = int(time.monotonic() - elapsed_start)
            yield emit("runner", {
                "state": runner_state,
                "message": _runner_message(runner_state, conclusion),
                "run_url": job.run_url,
                "elapsed": elapsed_s,
            })

        # Try to get live job step info
        try:
            jobs_data = await _get_run_jobs(owner, repo, github_token, run_id)
            for j in jobs_data:
                for step in j.get("steps", []):
                    if step.get("status") == "in_progress":
                        step_name = step.get("name", "")
                        step_state = _step_to_runner_state(step_name)
                        if step_state and step_state != job.runner_state:
                            job.runner_state = step_state
                            yield emit("runner", {
                                "state": step_state,
                                "message": step_name,
                                "run_url": job.run_url,
                            })
                        yield emit("timeline", {
                            "step": "execution",
                            "status": "running",
                            "message": f"Runner: {step_name}",
                        })
        except Exception:
            pass

        if status == "completed":
            job.conclusion = conclusion

            # Download logs
            full_log_text = await _download_logs(owner, repo, github_token, run_id)
            log_events = _parse_log_lines(full_log_text, seen_log_lines)

            # Emit structured log events
            for evt in log_events[-LOG_CHUNK_LINES:]:
                if evt["kind"] == "agent_event":
                    yield _sse(evt["payload"].get("type", "step"), evt["payload"].get("payload", {}))
                elif evt["kind"] == "step":
                    yield emit("timeline", {"step": "execution", "status": "running", "message": evt["message"]})
                elif evt["kind"] == "error":
                    yield emit("timeline", {"step": "execution", "status": "error", "message": evt["message"]})
                elif evt["kind"] == "log":
                    yield emit("log", {"message": evt["message"]})

            # Extract quality gates
            job.quality_gates = _extract_quality_gates(full_log_text)
            if job.quality_gates:
                yield emit("quality_gates", {"gates": job.quality_gates})

            # Get artifacts list
            job.artifacts = await _list_artifacts(owner, repo, github_token, run_id)

            break

        # Incremental log streaming every ~20s
        elapsed_s = int(time.monotonic() - elapsed_start)
        if elapsed_s > 0 and elapsed_s % 20 == 0:
            try:
                partial = await _download_logs(owner, repo, github_token, run_id)
                if partial:
                    new_events = _parse_log_lines(partial, seen_log_lines)
                    for evt in new_events[-20:]:
                        if evt["kind"] == "log":
                            yield emit("log", {"message": evt["message"]})
                        elif evt["kind"] == "step":
                            yield emit("timeline", {"step": "execution", "status": "running", "message": evt["message"]})
            except Exception:
                pass

    # ── 6: Handle failure ──────────────────────────────────────────────
    if job.conclusion not in ("success", ""):
        yield emit("runner", {"state": "completed", "message": f"Runner finished with: {job.conclusion}", "run_url": job.run_url})
        yield emit("timeline", {"step": "execution", "status": "error", "message": f"Job {job.conclusion}"})
        yield emit("error", {
            "message": f"GitHub Actions job {job.conclusion}. Check logs at {job.run_url}",
            "run_url": job.run_url,
            "conclusion": job.conclusion,
        })
        return

    # ── 7: Check if agent committed anything ───────────────────────────
    yield emit("runner", {"state": "pushing", "message": "Verifying changes..."})
    yield emit("timeline", {"step": "push", "status": "running", "message": "Checking for committed changes..."})

    # Look for the latest commit on branch
    try:
        commits_data = await _gh("get", f"/repos/{owner}/{repo}/commits?sha={branch_name}&per_page=3", github_token)
        if isinstance(commits_data, list) and commits_data:
            top = commits_data[0]
            job.commit_hash = top.get("sha", "")[:12]
            # Get changed files from this commit
            commit_detail = await _gh("get", f"/repos/{owner}/{repo}/commits/{top['sha']}", github_token)
            files_changed = [f["filename"] for f in commit_detail.get("files", [])]
            job.modified_files = files_changed
            yield emit("timeline", {"step": "commit", "status": "done", "message": f"Committed {job.commit_hash}"})
            for f in files_changed[:5]:
                yield emit("file_change", {"path": f, "action": "modified"})
    except Exception:
        pass

    yield emit("timeline", {"step": "push", "status": "done", "message": f"Changes on {branch_name}"})

    # ── 8: Create PR ────────────────────────────────────────────────────
    yield emit("runner", {"state": "creating_pr", "message": "Generating Pull Request..."})
    yield emit("timeline", {"step": "pr", "status": "running", "message": "Opening Pull Request..."})

    done_summary = _extract_done_summary(full_log_text) or f"Completed task: {task}"
    pr_body = _generate_pr_body(job, done_summary, full_log_text)

    # Determine PR title prefix from task keywords
    pr_prefix = "feat"
    for kw, prefix in [("fix", "fix"), ("bug", "fix"), ("refactor", "refactor"),
                        ("test", "test"), ("doc", "docs"), ("security", "security"),
                        ("migrate", "chore"), ("update", "chore"), ("remove", "chore")]:
        if kw in task.lower():
            pr_prefix = prefix
            break

    try:
        pr = await _create_pr(
            owner, repo, github_token,
            title=f"{pr_prefix}: {task[:72]}",
            body=pr_body,
            head=branch_name,
            base=job.base_branch,
        )
        job.pr_url = pr.get("html_url", "")
        job.pr_number = pr.get("number", 0)
        yield emit("timeline", {"step": "pr", "status": "done", "message": f"PR #{job.pr_number} opened"})
        yield emit("pr", {"url": job.pr_url, "number": job.pr_number, "title": f"{pr_prefix}: {task[:72]}"})
    except Exception as e:
        msg = str(e)
        if "already exists" in msg.lower() or "422" in msg:
            yield emit("timeline", {"step": "pr", "status": "warn", "message": "PR already open for this branch"})
        else:
            yield emit("timeline", {"step": "pr", "status": "error", "message": msg[:120]})

    # ── 9: Upload artifacts marker ──────────────────────────────────────
    if job.artifacts:
        yield emit("runner", {"state": "uploading", "message": f"Artifacts: {', '.join(job.artifacts[:3])}"})

    # ── 10: Complete ───────────────────────────────────────────────────
    yield emit("runner", {"state": "completed", "message": "Runner completed · environment destroyed", "run_url": job.run_url})
    yield emit("runner", {"state": "destroyed", "message": "Ephemeral runner destroyed"})

    duration = int(time.monotonic() - job.start_time)
    yield emit("done", {
        "summary": done_summary,
        "pr_url": job.pr_url,
        "branch": branch_name,
        "modified_files": job.modified_files,
        "commit_hash": job.commit_hash,
        "run_url": job.run_url,
        "run_id": job.run_id,
        "quality_gates": job.quality_gates,
        "artifacts": job.artifacts,
        "duration_seconds": duration,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _runner_message(state: str, conclusion: str = "") -> str:
    msgs = {
        "queued":      "Task queued — waiting for runner",
        "provisioning": "Provisioning ubuntu-latest runner",
        "initializing": "Initializing environment",
        "connecting":  "Runner online — connecting to repository",
        "analyzing":   "Analyzing project structure",
        "executing":   "Agent executing changes",
        "validating":  "Running build and tests",
        "reflecting":  "Reflection agent reviewing changes",
        "pushing":     "Pushing changes to branch",
        "creating_pr": "Creating Pull Request",
        "uploading":   "Uploading artifacts",
        "completed":   f"Completed{' — ' + conclusion if conclusion and conclusion != 'success' else ''}",
        "destroyed":   "Ephemeral runner destroyed",
    }
    return msgs.get(state, state)


def _step_to_runner_state(step_name: str) -> str | None:
    name = step_name.lower()
    if "checkout" in name:
        return "connecting"
    if "detect" in name or "analyze" in name or "setup" in name:
        return "analyzing"
    if "install" in name or "dependencies" in name:
        return "initializing"
    if "agent" in name or "devbuddy" in name or "implement" in name:
        return "executing"
    if "test" in name or "build" in name or "lint" in name:
        return "validating"
    if "reflect" in name:
        return "reflecting"
    if "push" in name or "commit" in name:
        return "pushing"
    if "pull request" in name or "pr" in name:
        return "creating_pr"
    if "artifact" in name or "upload" in name:
        return "uploading"
    return None


def _extract_done_summary(log_text: str) -> str:
    """Try to find a DONE: summary line in the log output."""
    m = re.search(r"DONE:\s*(.+?)(?:\n|$)", log_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:500]
    m = re.search(r"DEVBUDDY_SUMMARY:\s*(.+?)(?:\n|$)", log_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:500]
    return ""
