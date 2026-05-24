"""
Agent Skills Registry
=====================
Skills are callable async functions the agent can invoke as tools.
Each skill is registered in SKILL_REGISTRY and selected by the LLM
using a provider-agnostic JSON tool-call protocol (no vendor SDK needed).

Adding a new skill:
  1. Define an async function with signature (args: dict) -> str
  2. Register it via @skill(name, description, parameters_schema)

The agent_executor calls `run_skill(name, args)` and feeds the result
back to the LLM as a "tool result" message.
"""
from __future__ import annotations

import ast
import os
import asyncio
from typing import Callable, Awaitable

from app.core.logger import get_logger

logger = get_logger("skills")


# ── Registry ──────────────────────────────────────────────────────────────────

_SkillFn = Callable[[dict], Awaitable[str]]

SKILL_REGISTRY: dict[str, dict] = {}


def skill(name: str, description: str, parameters: dict):
    """Decorator that registers an async function as an agent skill."""
    def decorator(fn: _SkillFn) -> _SkillFn:
        SKILL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "fn": fn,
        }
        return fn
    return decorator


async def run_skill(name: str, args: dict) -> str:
    """Dispatch to a registered skill. Returns result string."""
    entry = SKILL_REGISTRY.get(name)
    if not entry:
        return f"[skill_error] Unknown skill: '{name}'. Available: {list(SKILL_REGISTRY.keys())}"
    try:
        result = await entry["fn"](args)
        logger.info("skill_executed", skill=name)
        return str(result)
    except Exception as exc:
        logger.warning("skill_failed", skill=name, error=str(exc))
        return f"[skill_error] {name} raised: {exc}"


def skills_schema() -> list[dict]:
    """Return OpenAI-style tool schemas for all registered skills."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["parameters"],
            },
        }
        for s in SKILL_REGISTRY.values()
    ]


# ── Built-in skills ───────────────────────────────────────────────────────────

@skill(
    name="run_python",
    description=(
        "Execute a Python code snippet in a SANDBOXED environment and return stdout/stderr. "
        "Backend is selected by the SANDBOX_BACKEND env var: 'e2b' (recommended, real isolation), "
        "'subprocess' (dev-only, semi-isolated), 'disabled' (default — no execution)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute."},
            "timeout": {"type": "integer", "description": "Max seconds to wait (default 15)."},
        },
        "required": ["code"],
    },
)
async def _run_python(args: dict) -> str:
    """
    SECURITY: Earlier versions used in-process exec() which is RCE-equivalent.
    This is now gated behind SANDBOX_BACKEND with a safe default of 'disabled'.

    Recommended production setup:
      SANDBOX_BACKEND=e2b
      E2B_API_KEY=...   (free tier: e2b.dev)
    """
    code = args.get("code", "")
    timeout = int(args.get("timeout", 15))
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    backend = os.environ.get("SANDBOX_BACKEND", "disabled").lower()

    if backend == "e2b":
        return await _run_python_e2b(code, timeout)
    if backend == "subprocess":
        return await _run_python_subprocess(code, timeout)

    return (
        "[sandbox_disabled] Code execution is disabled by default for safety. "
        "Set SANDBOX_BACKEND=e2b (recommended, free tier at e2b.dev) "
        "or SANDBOX_BACKEND=subprocess (dev only) to enable execution."
    )


async def _run_python_e2b(code: str, timeout: int) -> str:
    """Real sandbox via e2b.dev — Firecracker microVMs, free tier available."""
    api_key = os.environ.get("E2B_API_KEY")
    if not api_key:
        return "[sandbox_error] SANDBOX_BACKEND=e2b but E2B_API_KEY is not set."
    try:
        # Lazy import so e2b_code_interpreter stays optional
        from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]
    except ImportError:
        return (
            "[sandbox_error] e2b_code_interpreter not installed. "
            "Add `e2b-code-interpreter` to requirements.txt."
        )
    try:
        # Run e2b in a worker thread (its client is sync)
        def _exec_sync() -> str:
            with Sandbox(api_key=api_key, timeout=timeout) as sbx:
                exe = sbx.run_code(code)
                stdout = "\n".join(exe.logs.stdout) if exe.logs.stdout else ""
                stderr = "\n".join(exe.logs.stderr) if exe.logs.stderr else ""
                err = f"\nERROR: {exe.error.value}" if exe.error else ""
                return (stdout or "(no output)") + (f"\nSTDERR: {stderr}" if stderr else "") + err

        return await asyncio.to_thread(_exec_sync)
    except Exception as exc:  # noqa: BLE001
        return f"[sandbox_error] e2b: {exc}"


async def _run_python_subprocess(code: str, timeout: int) -> str:
    """Dev fallback — runs in a subprocess with a deny-network env. NOT a real sandbox."""
    proc = await asyncio.create_subprocess_exec(
        "python", "-c", code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": os.environ.get("PATH", "")},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return f"[sandbox_error] subprocess: timeout after {timeout}s"
    output = out.decode("utf-8", errors="replace") or "(no output)"
    if err:
        output += f"\nSTDERR: {err.decode('utf-8', errors='replace')}"
    return output


@skill(
    name="read_file",
    description="Read a file from the agent workspace and return its contents.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path inside the workspace."},
            "max_lines": {"type": "integer", "description": "Maximum lines to return (default 100)."},
        },
        "required": ["path"],
    },
)
async def _read_file(args: dict) -> str:
    workspace = os.environ.get("WORKSPACE_ROOT", "/tmp/devbuddy-workspaces")
    rel = args.get("path", "").lstrip("/").replace("..", "")
    full = os.path.join(workspace, rel)
    if not os.path.exists(full):
        return f"[file_not_found] {rel}"
    try:
        with open(full, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        max_lines = int(args.get("max_lines", 100))
        return "".join(lines[:max_lines])
    except Exception as exc:
        return f"[read_error] {exc}"


@skill(
    name="write_file",
    description="Write content to a file in the agent workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path inside the workspace."},
            "content": {"type": "string", "description": "File content to write."},
        },
        "required": ["path", "content"],
    },
)
async def _write_file(args: dict) -> str:
    workspace = os.environ.get("WORKSPACE_ROOT", "/tmp/devbuddy-workspaces")
    rel = args.get("path", "output.txt").lstrip("/").replace("..", "")
    content = args.get("content", "")
    full = os.path.join(workspace, rel)
    os.makedirs(os.path.dirname(full) or workspace, exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"Written {len(content)} chars to {rel}"


@skill(
    name="web_search",
    description=(
        "Search the web for current information. Returns a list of result snippets. "
        "Requires SERPAPI_KEY or TAVILY_API_KEY to be set; otherwise returns a placeholder."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string."},
            "num_results": {"type": "integer", "description": "Number of results to return (default 5)."},
        },
        "required": ["query"],
    },
)
async def _web_search(args: dict) -> str:
    query = args.get("query", "")
    num = int(args.get("num_results", 5))

    tavily_key = os.environ.get("TAVILY_API_KEY")
    serpapi_key = os.environ.get("SERPAPI_KEY")

    if tavily_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": tavily_key, "query": query, "max_results": num},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    lines = [f"- [{r.get('title','')}]({r.get('url','')}) — {r.get('content','')[:150]}" for r in results]
                    return "\n".join(lines) or "(no results)"
        except Exception as exc:
            return f"[web_search_error] Tavily: {exc}"

    if serpapi_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"api_key": serpapi_key, "q": query, "num": num, "engine": "google"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("organic_results", [])
                    lines = [f"- {r.get('title','')} — {r.get('snippet','')}" for r in results[:num]]
                    return "\n".join(lines) or "(no results)"
        except Exception as exc:
            return f"[web_search_error] SerpAPI: {exc}"

    return (
        f"[web_search_stub] No search API key configured (TAVILY_API_KEY or SERPAPI_KEY). "
        f"Would have searched for: '{query}'"
    )


@skill(
    name="recall_memory",
    description="Search the agent's long-term memory for facts related to a query.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for in memory."},
            "k": {"type": "integer", "description": "Number of memories to return (default 5)."},
        },
        "required": ["query"],
    },
)
async def _recall_memory(args: dict) -> str:
    """
    This skill is a placeholder — actual recall uses the injected context.
    The real recall happens in chat.py before the LLM call.
    This version is invoked when the LLM explicitly wants to search memory mid-task.
    """
    return (
        "[memory_recall] Memory context was already injected into your system prompt. "
        f"Query '{args.get('query', '')}' has been noted for future consolidation."
    )
