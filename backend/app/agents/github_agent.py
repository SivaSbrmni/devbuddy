"""GitHub-Native Autonomous Engineering Agent.

ReAct loop: THINK → ACT → OBSERVE → REFLECT → REPLAN → CONTINUE

Operates entirely inside a real GitHub repository:
  - clones / reuses workspace
  - creates an isolated devbuddy/{task} branch
  - plans, executes, validates changes
  - commits and pushes
  - opens a Pull Request
  - streams every step as SSE events
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx
import structlog

from app.core.config import settings
from app.core.model_router import LLMRequest, ModelRouter, TaskCategory

log = structlog.get_logger()

GITHUB_API = "https://api.github.com"
MAX_REACT_ITERATIONS = 12
WORKSPACE_BASE = Path(settings.REPOS_ROOT)


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    conversation_id: str
    task_id: str
    github_token: str
    owner: str
    repo: str
    default_branch: str
    task: str
    branch: str = ""
    workspace_path: Path = field(default_factory=Path)
    plan: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    execution_history: list[dict] = field(default_factory=list)
    validation_results: dict = field(default_factory=dict)
    commit_hash: str = ""
    pull_request_url: str = ""
    status: str = "initializing"
    errors: list[str] = field(default_factory=list)
    tokens_used: int = 0
    start_time: float = field(default_factory=time.monotonic)


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(event_type: str, payload: dict) -> str:
    data = json.dumps({
        "type": event_type,
        "timestamp": int(time.time() * 1000),
        "payload": payload,
    })
    return f"data: {data}\n\n"


# ── GitHub API helpers ────────────────────────────────────────────────────────

async def _gh(method: str, path: str, token: str, **kwargs) -> dict | list:
    async with httpx.AsyncClient(timeout=30) as client:
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
            raise RuntimeError(f"GitHub API {method.upper()} {path} → {resp.status_code}: {resp.text[:300]}")
        if resp.content:
            return resp.json()
        return {}


async def _get_repo_info(owner: str, repo: str, token: str) -> dict:
    return await _gh("get", f"/repos/{owner}/{repo}", token)


async def _create_branch(owner: str, repo: str, token: str, branch: str, from_sha: str) -> None:
    await _gh("post", f"/repos/{owner}/{repo}/git/refs", token, json={
        "ref": f"refs/heads/{branch}",
        "sha": from_sha,
    })


async def _get_default_sha(owner: str, repo: str, token: str, branch: str) -> str:
    data = await _gh("get", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token)
    return data["object"]["sha"]  # type: ignore


async def _create_pr(owner: str, repo: str, token: str, title: str, body: str, head: str, base: str) -> dict:
    return await _gh("post", f"/repos/{owner}/{repo}/pulls", token, json={
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "draft": False,
    })


async def _get_file_tree(owner: str, repo: str, token: str, branch: str) -> list[str]:
    try:
        data = await _gh("get", f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", token)
        return [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]  # type: ignore
    except Exception:
        return []


async def _get_file_content(owner: str, repo: str, token: str, path: str, branch: str) -> str:
    try:
        import base64
        data = await _gh("get", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}", token)
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")  # type: ignore
    except Exception:
        return ""


# ── Workspace (local git clone) ───────────────────────────────────────────────

async def _run(cmd: str, cwd: Path, env: dict | None = None) -> tuple[int, str, str]:
    """Run a shell command, return (exit_code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=300)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Command timed out"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def _ensure_workspace(state: AgentState) -> Path:
    """Clone or reuse a local workspace for the repo."""
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    ws_key = f"{state.owner}__{state.repo}"
    ws_path = WORKSPACE_BASE / ws_key

    clone_url = f"https://x-access-token:{state.github_token}@github.com/{state.owner}/{state.repo}.git"

    if ws_path.exists():
        # Reuse — fetch latest
        code, _, err = await _run("git fetch --all --prune", ws_path)
        if code != 0:
            shutil.rmtree(ws_path, ignore_errors=True)

    if not ws_path.exists():
        code, out, err = await _run(
            f"git clone --depth 50 {clone_url} {ws_path}",
            WORKSPACE_BASE,
        )
        if code != 0:
            raise RuntimeError(f"Clone failed: {err[:400]}")

    # Configure git identity
    await _run('git config user.email "devbuddy@devbuddy.org"', ws_path)
    await _run('git config user.name "DevBuddy Agent"', ws_path)
    # Update remote URL with fresh token
    await _run(f"git remote set-url origin {clone_url}", ws_path)

    return ws_path


async def _checkout_branch(ws_path: Path, branch: str, base_branch: str) -> tuple[int, str]:
    """Create or checkout a devbuddy branch."""
    # Fetch to make sure base exists
    await _run(f"git fetch origin {base_branch}", ws_path)
    # Check if branch already exists remotely
    code, out, _ = await _run(f"git ls-remote --heads origin {branch}", ws_path)
    if out.strip():
        # Already exists — checkout
        code, _, err = await _run(f"git checkout {branch} && git pull origin {branch}", ws_path)
    else:
        # Create from base
        code, _, err = await _run(
            f"git checkout origin/{base_branch} -b {branch}", ws_path
        )
    return code, branch


# ── LLM helpers ──────────────────────────────────────────────────────────────

async def _llm(router: ModelRouter, messages: list[dict], system: str = "", max_tokens: int = 4096) -> str:
    resp = await router.complete(LLMRequest(
        messages=messages,
        task_category=TaskCategory.CODING,
        system_prompt=system,
        max_tokens=max_tokens,
        temperature=0.1,
    ))
    return resp.content


# ── Tool implementations ──────────────────────────────────────────────────────

TOOLS_SCHEMA = [
    {"name": "read_file", "description": "Read a file from the workspace", "params": ["path"]},
    {"name": "write_file", "description": "Write/create a file in the workspace", "params": ["path", "content"]},
    {"name": "edit_file", "description": "Replace a string in a file", "params": ["path", "old_str", "new_str"]},
    {"name": "list_files", "description": "List files matching a pattern", "params": ["pattern"]},
    {"name": "search_code", "description": "Search for text in the workspace", "params": ["query"]},
    {"name": "run_command", "description": "Run a safe shell command (no destructive ops)", "params": ["command"]},
    {"name": "create_file", "description": "Create a new file (fails if exists)", "params": ["path", "content"]},
    {"name": "delete_file", "description": "Delete a file from workspace", "params": ["path"]},
]

BLOCKED_COMMANDS = {"rm -rf /", "format", "dd if=", "mkfs", "> /dev/", "curl | bash", "wget | sh"}


async def run_tool(name: str, params: dict, state: AgentState) -> dict:
    """Execute a tool, return {output, error, modified_file}."""
    ws = state.workspace_path

    if name == "read_file":
        p = ws / params["path"]
        if not p.exists():
            return {"error": f"File not found: {params['path']}"}
        content = p.read_text(errors="replace")
        return {"output": content[:8000]}

    elif name == "write_file":
        p = ws / params["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(params["content"])
        if params["path"] not in state.modified_files:
            state.modified_files.append(params["path"])
        return {"output": f"Written: {params['path']}"}

    elif name == "create_file":
        p = ws / params["path"]
        if p.exists():
            return {"error": f"File already exists: {params['path']}"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(params["content"])
        if params["path"] not in state.modified_files:
            state.modified_files.append(params["path"])
        return {"output": f"Created: {params['path']}"}

    elif name == "edit_file":
        p = ws / params["path"]
        if not p.exists():
            return {"error": f"File not found: {params['path']}"}
        content = p.read_text(errors="replace")
        old = params["old_str"]
        new = params["new_str"]
        if old not in content:
            return {"error": f"String not found in {params['path']}: {old[:80]}..."}
        p.write_text(content.replace(old, new, 1))
        if params["path"] not in state.modified_files:
            state.modified_files.append(params["path"])
        return {"output": f"Edited: {params['path']}"}

    elif name == "delete_file":
        p = ws / params["path"]
        if p.exists():
            p.unlink()
        return {"output": f"Deleted: {params['path']}"}

    elif name == "list_files":
        pattern = params.get("pattern", "*")
        matches = sorted([str(f.relative_to(ws)) for f in ws.rglob(pattern) if f.is_file()])[:100]
        return {"output": "\n".join(matches)}

    elif name == "search_code":
        query = params["query"]
        code, out, _ = await _run(f'grep -r --include="*" -l "{query}" . 2>/dev/null | head -20', ws)
        return {"output": out or "No matches"}

    elif name == "run_command":
        cmd = params["command"]
        # Safety check
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd:
                return {"error": f"Blocked command: {cmd}"}
        # Disallow git push/commit here — agent does that via controlled path
        if any(x in cmd for x in ["git push", "git commit", "git checkout"]):
            return {"error": "Use the agent's built-in git operations, not run_command"}
        code, out, err = await _run(cmd, ws)
        combined = (out + err)[:4000]
        return {"output": combined, "exit_code": code}

    return {"error": f"Unknown tool: {name}"}


# ── ReAct Loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are DevBuddy, an autonomous software engineer working inside a real GitHub repository.

You follow the ReAct pattern:
1. THOUGHT: Reason about what to do next
2. ACTION: Call exactly one tool
3. OBSERVATION: Read the tool output
4. REPEAT until the task is complete, then output DONE

Available tools:
{tools}

Rules:
- Never modify main/master branch files directly (you're on a devbuddy branch)
- Never run destructive commands
- Always read a file before editing it
- Write clean, production-quality code
- Follow existing code style and conventions
- Run build/test commands to validate changes

Output format for each step:
THOUGHT: <your reasoning>
ACTION: <tool_name>
PARAMS: <json params>

When finished:
DONE: <summary of all changes made>
"""


def _parse_react_step(text: str) -> tuple[str, str, dict] | tuple[None, None, None]:
    """Parse a THOUGHT/ACTION/PARAMS block."""
    thought_m = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|$)", text, re.DOTALL)
    action_m = re.search(r"ACTION:\s*(\w+)", text)
    params_m = re.search(r"PARAMS:\s*(\{.+?\})", text, re.DOTALL)
    done_m = re.search(r"DONE:\s*(.+)", text, re.DOTALL)

    if done_m:
        return "DONE", done_m.group(1).strip(), {}

    if not action_m:
        return None, None, None

    thought = thought_m.group(1).strip() if thought_m else ""
    action = action_m.group(1).strip()
    params: dict = {}
    if params_m:
        try:
            params = json.loads(params_m.group(1))
        except json.JSONDecodeError:
            pass
    return thought, action, params


# ── Main Agent ────────────────────────────────────────────────────────────────

async def run_github_agent(
    task: str,
    owner: str,
    repo: str,
    github_token: str,
    router: ModelRouter,
    conversation_id: str = "",
) -> AsyncGenerator[str, None]:
    """Full autonomous GitHub engineering agent. Yields SSE strings."""

    task_id = str(uuid.uuid4())[:8]
    branch_name = f"devbuddy/{re.sub(r'[^a-z0-9-]', '-', task[:40].lower()).strip('-')}-{task_id}"

    state = AgentState(
        conversation_id=conversation_id or task_id,
        task_id=task_id,
        github_token=github_token,
        owner=owner,
        repo=repo,
        default_branch="main",
        task=task,
        branch=branch_name,
    )

    def emit(event: str, payload: dict) -> str:
        return _sse(event, payload)

    # ── 0: Repo info ──────────────────────────────────────────────────
    yield emit("timeline", {"step": "init", "status": "running", "message": f"Connecting to {owner}/{repo}..."})
    try:
        repo_info = await _get_repo_info(owner, repo, github_token)
        state.default_branch = repo_info.get("default_branch", "main")
        yield emit("timeline", {"step": "init", "status": "done", "message": f"Repository ready · {state.default_branch}"})
    except Exception as e:
        yield emit("error", {"message": f"Cannot access repository: {e}"})
        return

    # ── 1: Clone / reuse workspace ────────────────────────────────────
    yield emit("timeline", {"step": "workspace", "status": "running", "message": "Preparing workspace..."})
    try:
        ws_path = await _ensure_workspace(state)
        state.workspace_path = ws_path
        yield emit("timeline", {"step": "workspace", "status": "done", "message": f"Workspace ready at {ws_path.name}"})
    except Exception as e:
        yield emit("error", {"message": f"Workspace setup failed: {e}"})
        return

    # ── 2: Create branch ──────────────────────────────────────────────
    yield emit("timeline", {"step": "branch", "status": "running", "message": f"Creating branch {branch_name}..."})
    try:
        code, branch = await _checkout_branch(ws_path, branch_name, state.default_branch)
        if code != 0:
            raise RuntimeError(f"Branch checkout failed (code {code})")
        yield emit("timeline", {"step": "branch", "status": "done", "message": f"On branch {branch_name}"})
        yield emit("branch", {"name": branch_name})
    except Exception as e:
        yield emit("error", {"message": f"Branch creation failed: {e}"})
        return

    # ── 3: Project analysis ───────────────────────────────────────────
    yield emit("timeline", {"step": "analysis", "status": "running", "message": "Analyzing project structure..."})
    try:
        file_tree = await _get_file_tree(owner, repo, github_token, state.default_branch)
        tree_str = "\n".join(file_tree[:150])

        # Read key config files to understand the stack
        key_files = []
        for fname in ["package.json", "requirements.txt", "pom.xml", "go.mod", "Cargo.toml",
                       "pyproject.toml", "build.gradle", "README.md"]:
            if fname in file_tree:
                content = await _get_file_content(owner, repo, github_token, fname, state.default_branch)
                if content:
                    key_files.append(f"=== {fname} ===\n{content[:1500]}")

        project_context = f"Repository: {owner}/{repo}\n\nFile tree:\n{tree_str}\n\n"
        if key_files:
            project_context += "Key files:\n" + "\n\n".join(key_files)

        yield emit("timeline", {"step": "analysis", "status": "done", "message": f"Analyzed {len(file_tree)} files"})
        yield emit("analysis", {"file_count": len(file_tree), "tree_preview": tree_str[:800]})
    except Exception as e:
        project_context = f"Repository: {owner}/{repo}"
        yield emit("timeline", {"step": "analysis", "status": "warn", "message": f"Partial analysis: {e}"})

    # ── 4: Planning ───────────────────────────────────────────────────
    yield emit("timeline", {"step": "planning", "status": "running", "message": "Creating execution plan..."})
    try:
        plan_prompt = f"""You are a senior software engineer. Given this task and project context, create a precise step-by-step implementation plan.

Task: {task}

Project context:
{project_context[:3000]}

Output a numbered list of concrete implementation steps. Each step should be a specific action (read file X, add function Y to Z, run command W). Maximum 10 steps."""

        plan_text = await _llm(router, [{"role": "user", "content": plan_prompt}], max_tokens=1024)
        plan_steps = [line.strip() for line in plan_text.strip().split("\n") if re.match(r"^\d+\.", line.strip())]
        if not plan_steps:
            plan_steps = [s.strip() for s in plan_text.strip().split("\n") if s.strip()][:10]
        state.plan = plan_steps

        yield emit("timeline", {"step": "planning", "status": "done", "message": f"Plan ready · {len(plan_steps)} steps"})
        yield emit("plan", {"steps": plan_steps})
    except Exception as e:
        state.plan = ["Implement the requested changes"]
        yield emit("timeline", {"step": "planning", "status": "warn", "message": f"Used default plan: {e}"})

    # ── 5: ReAct execution loop ───────────────────────────────────────
    yield emit("timeline", {"step": "execution", "status": "running", "message": "Executing changes..."})

    tools_desc = "\n".join(f"- {t['name']}({', '.join(t['params'])}): {t['description']}" for t in TOOLS_SCHEMA)
    system = SYSTEM_PROMPT.format(tools=tools_desc)

    messages: list[dict] = [{
        "role": "user",
        "content": (
            f"Task: {task}\n\n"
            f"Repository: {owner}/{repo} (branch: {branch_name})\n\n"
            f"Project context:\n{project_context[:2500]}\n\n"
            f"Implementation plan:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(state.plan)) +
            "\n\nBegin. For each step: THOUGHT → ACTION → PARAMS. When all steps are done: DONE: <summary>"
        ),
    }]

    iteration = 0
    done_summary = ""

    while iteration < MAX_REACT_ITERATIONS:
        iteration += 1

        try:
            response = await _llm(router, messages, system=system, max_tokens=2048)
        except Exception as e:
            yield emit("error", {"message": f"LLM error on iteration {iteration}: {e}"})
            break

        messages.append({"role": "assistant", "content": response})

        thought, action, params = _parse_react_step(response)

        if action == "DONE":
            done_summary = thought or ""
            yield emit("timeline", {"step": "execution", "status": "done", "message": "Changes complete"})
            break

        if not action:
            yield emit("thinking", {"text": response[:400]})
            break

        # Emit thought
        if thought:
            state.reasoning.append(thought)
            yield emit("thinking", {"iteration": iteration, "thought": thought})

        # Execute tool
        yield emit("tool_call", {"iteration": iteration, "tool": action, "params": {k: str(v)[:200] for k, v in params.items()}})

        tool_result = await run_tool(action, params, state)
        state.tool_calls.append({"tool": action, "params": params, "result": tool_result})

        # Emit file change if applicable
        if action in ("write_file", "create_file", "edit_file") and "error" not in tool_result:
            yield emit("file_change", {"path": params.get("path", ""), "action": action})

        observation = tool_result.get("output") or tool_result.get("error", "No output")
        messages.append({"role": "user", "content": f"OBSERVATION: {observation[:3000]}"})

        yield emit("observation", {"iteration": iteration, "tool": action, "output": observation[:500]})

    # ── 6: Commit and push ────────────────────────────────────────────
    if not state.modified_files:
        yield emit("timeline", {"step": "commit", "status": "skip", "message": "No files modified"})
        yield emit("done", {"summary": done_summary or "No changes made", "pr_url": "", "branch": branch_name, "modified_files": []})
        return

    yield emit("timeline", {"step": "commit", "status": "running", "message": f"Committing {len(state.modified_files)} file(s)..."})
    try:
        commit_msg = f"feat(devbuddy): {task[:72]}\n\nAutonomous implementation by DevBuddy Agent\nTask ID: {state.task_id}"
        code, out, err = await _run("git add -A", ws_path)
        code, out, err = await _run(f'git commit -m "{commit_msg}"', ws_path)
        if code != 0 and "nothing to commit" not in (out + err):
            raise RuntimeError(f"Commit failed: {err[:300]}")

        # Extract commit hash
        _, hash_out, _ = await _run("git rev-parse HEAD", ws_path)
        state.commit_hash = hash_out.strip()[:12]
        yield emit("timeline", {"step": "commit", "status": "done", "message": f"Committed {state.commit_hash}"})
    except Exception as e:
        yield emit("timeline", {"step": "commit", "status": "error", "message": str(e)})

    # ── 7: Push ───────────────────────────────────────────────────────
    yield emit("timeline", {"step": "push", "status": "running", "message": f"Pushing to origin/{branch_name}..."})
    try:
        code, out, err = await _run(f"git push --set-upstream origin {branch_name}", ws_path)
        if code != 0:
            raise RuntimeError(f"Push failed: {err[:300]}")
        yield emit("timeline", {"step": "push", "status": "done", "message": "Pushed to GitHub"})
    except Exception as e:
        yield emit("timeline", {"step": "push", "status": "error", "message": str(e)})
        yield emit("done", {"summary": done_summary, "pr_url": "", "branch": branch_name, "modified_files": state.modified_files})
        return

    # ── 8: Pull Request ───────────────────────────────────────────────
    yield emit("timeline", {"step": "pr", "status": "running", "message": "Opening Pull Request..."})
    try:
        pr_body = (
            f"## Changes\n\n{done_summary}\n\n"
            f"## Modified Files\n\n" + "\n".join(f"- `{f}`" for f in state.modified_files) +
            f"\n\n## Plan\n\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(state.plan)) +
            f"\n\n---\n*Autonomous implementation by [DevBuddy](https://devbuddy.org) · Task `{state.task_id}`*"
        )
        pr = await _create_pr(
            owner, repo, github_token,
            title=f"feat: {task[:72]}",
            body=pr_body,
            head=branch_name,
            base=state.default_branch,
        )
        state.pull_request_url = pr.get("html_url", "")
        pr_number = pr.get("number", "")
        yield emit("timeline", {"step": "pr", "status": "done", "message": f"PR #{pr_number} opened"})
        yield emit("pr", {"url": state.pull_request_url, "number": pr_number, "title": f"feat: {task[:72]}"})
    except Exception as e:
        yield emit("timeline", {"step": "pr", "status": "error", "message": str(e)})

    # ── 9: Done ───────────────────────────────────────────────────────
    duration = int(time.monotonic() - state.start_time)
    yield emit("done", {
        "summary": done_summary or f"Completed {len(state.modified_files)} file changes",
        "pr_url": state.pull_request_url,
        "branch": branch_name,
        "modified_files": state.modified_files,
        "commit_hash": state.commit_hash,
        "tool_calls": len(state.tool_calls),
        "iterations": iteration,
        "duration_seconds": duration,
    })
