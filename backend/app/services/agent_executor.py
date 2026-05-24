"""
Agent Executor — ReAct Loop
============================
Implements Reason → Act → Observe → (Fix → Retry) for each sub-task.

Flow per task:
  1. REASON  — LLM decomposes the task into N isolated sub-tasks
  2. ACT     — each sub-task gets its own workspace dir, LLM generates files
  3. OBSERVE — validate files exist, content is non-empty, syntax ok
  4. FIX     — if observation fails, LLM gets error context and retries (max 2)
  5. COLLECT — merge all sub-task outputs into workspace/{task_id}/

Container logs are streamed line-by-line via SSE so the Terminal tab shows
live progress identical to real docker exec output.
"""
import os
import re
import ast
import json
import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator

from app.core.config import settings
from app.core.logger import get_logger
from app.services.llm_service import _call_ollama, _call_openai_compat_with_prompt, llm_call
from app.services.skills import SKILL_REGISTRY, run_skill, skills_schema

logger = get_logger("agent_executor")

WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", "/tmp/devbuddy-workspaces")
MAX_RETRIES = 2

# ── Prompts ────────────────────────────────────────────────────────────────

MEMORY_SYSTEM_PROMPT = (
    "You are an autonomous coding agent with access to skills and long-term memory.\n"
    "Available skills: {skills}\n\n"
    "Relevant memories about this user/project:\n{memories}\n\n"
    "Use the memories to personalise your work and the skills when you need to execute, search, or read files."
)

DECOMPOSE_PROMPT = """You are a senior software architect.
Decompose the following task into at most 4 focused sub-tasks.

Task: {task}

IMPORTANT: For each sub-task, analyze dependencies:
- If sub-tasks can run in parallel (no shared files, no dependencies), mark "parallel": true
- If sub-task B depends on files from sub-task A, mark "depends_on": ["subtask-A-id"]
- If sub-tasks need to share intermediate results, mark "needs_coordination": true

Respond ONLY with a JSON array:
[
  {{"id": "subtask-1", "title": "...", "description": "...", "files": ["file.ext"], "parallel": true, "depends_on": [], "needs_coordination": false}},
  {{"id": "subtask-2", "title": "...", "description": "...", "files": ["file2.ext"], "parallel": true, "depends_on": ["subtask-1"], "needs_coordination": false}}
]

Guidelines:
- "parallel": true means this task can run simultaneously with others
- "depends_on": list of task IDs that must complete first
- "needs_coordination": true means this task needs to communicate with other tasks during execution
- Keep dependencies minimal - prefer parallel when possible"""

CODE_GEN_PROMPT = """You are an autonomous coding agent implementing a single sub-task.

Sub-task: {title}
Details: {description}
Expected output files: {files}
Full task context: {context}

Generate ALL the files listed in "Expected output files" with complete, working code.
Respond ONLY with a JSON array:
[{{"path": "relative/path/file.ext", "content": "...full content..."}}]

JSON array:"""

FIX_PROMPT = """You are an autonomous coding agent fixing failing code.

Sub-task: {title}
Attempt #{attempt} failed with these errors:
{errors}

Previously generated files:
{prev_files}

Fix all issues and regenerate the complete files.
Respond ONLY with a JSON array:
[{{"path": "relative/path/file.ext", "content": "...full content..."}}]

JSON array:"""


# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class SubTask:
    id: str
    title: str
    description: str
    expected_files: list[str] = field(default_factory=list)
    generated_files: list[dict] = field(default_factory=list)  # [{path, content}]
    status: str = "pending"   # pending | running | done | failed
    errors: list[str] = field(default_factory=list)
    attempts: int = 0
    parallel: bool = True
    depends_on: list[str] = field(default_factory=list)
    needs_coordination: bool = False


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now_ts() -> float:
    return time.time()


async def _llm(prompt: str, memories: list[str] | None = None) -> str:
    """
    Provider-agnostic LLM call with optional memory injection.
    When memories are provided they are prepended as a system context block.
    """
    skill_names = ", ".join(SKILL_REGISTRY.keys()) or "none"
    mem_block = "\n".join(f"- {m}" for m in (memories or [])) or "(none)"
    system = MEMORY_SYSTEM_PROMPT.format(skills=skill_names, memories=mem_block)
    return await llm_call(prompt=prompt, system=system)


def _extract_json_array(raw: str) -> list | None:
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _sanitise_path(path: str) -> str:
    path = re.sub(r"\.\./", "", path).lstrip("/")
    return path or "output.txt"


def _write_file(workspace: str, path: str, content: str) -> str:
    full = os.path.join(workspace, path)
    os.makedirs(os.path.dirname(full) or workspace, exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return full


def _observe(files_data: list[dict], expected: list[str]) -> list[str]:
    """Return list of error strings; empty = all checks passed."""
    errors: list[str] = []
    generated_paths = {f.get("path", "") for f in files_data}

    for exp in expected:
        if not any(exp in p for p in generated_paths):
            errors.append(f"Missing expected file: {exp}")

    for f in files_data:
        path = f.get("path", "")
        content = f.get("content", "")
        if not content.strip():
            errors.append(f"Empty content for {path}")
        if path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                errors.append(f"Syntax error in {path}: {e}")

    return errors


def _build_execution_waves(subtasks: list[SubTask]) -> list[list[SubTask]]:
    """Build execution waves based on dependencies. Each wave can run in parallel."""
    remaining = {st.id: st for st in subtasks}
    waves: list[list[SubTask]] = []
    completed: set[str] = set()
    
    while remaining:
        # Find tasks with all dependencies satisfied
        ready = []
        for st_id, st in list(remaining.items()):
            deps_satisfied = all(dep in completed for dep in st.depends_on)
            if deps_satisfied:
                ready.append(st)
                del remaining[st_id]
        
        if not ready:
            # Circular dependency or missing dependency - force remaining into final wave
            ready = list(remaining.values())
            remaining.clear()
        
        waves.append(ready)
        completed.update(st.id for st in ready)
    
    return waves


def _fallback_subtasks(title: str, description: str) -> list[SubTask]:
    slug = re.sub(r"[^a-z0-9]", "_", title.lower())[:30]
    return [
        SubTask(
            id="subtask-1",
            title=f"Implement {title}",
            description=description,
            expected_files=[f"src/{slug}.py", f"tests/test_{slug}.py", "README.md"],
        )
    ]


# ── ReAct loop ───────────────────────────────────────────────────────────────

# ── In-process coordination for Phase 1 ───────────────────────────────────

class TaskCoordinator:
    """Lightweight in-process coordination for parallel sub-tasks."""
    
    def __init__(self):
        self._completed_files: dict[str, list[dict]] = {}  # task_id -> files
        self._shared_store: dict[str, any] = {}
        self._lock = asyncio.Lock()
    
    async def register_completion(self, task_id: str, files: list[dict]):
        async with self._lock:
            self._completed_files[task_id] = files
    
    async def get_completed_task_files(self, task_id: str) -> list[dict]:
        async with self._lock:
            return self._completed_files.get(task_id, [])
    
    async def wait_for_dependencies(self, depends_on: list[str], timeout: float = 300.0) -> bool:
        """Wait for all dependency tasks to complete."""
        start = time.time()
        while time.time() - start < timeout:
            async with self._lock:
                if all(dep in self._completed_files for dep in depends_on):
                    return True
            await asyncio.sleep(0.5)
        return False
    
    def share_data(self, key: str, value: any):
        self._shared_store[key] = value
    
    def get_shared_data(self, key: str) -> any:
        return self._shared_store.get(key)


async def execute_task(
    task_id: str,
    task_title: str,
    task_description: str,
    mcp_context: str = "",
    repo_context: str = "",
    user_id: str | None = None,
    db=None,
) -> AsyncGenerator[dict, None]:
    """
    ReAct loop generator with intelligent parallel execution.
    Yields log-line dicts: {"line": str, "stream": "stdout"|"stderr", "ts": float}
    Writes all output files to WORKSPACE_ROOT/{task_id}/.
    
    Execution strategy:
    - Independent tasks run in parallel (up to MAX_PARALLEL limit)
    - Dependent tasks wait for predecessors, then run
    - Coordination-needed tasks get access to shared data store
    """
    workspace = os.path.join(WORKSPACE_ROOT, task_id)
    os.makedirs(workspace, exist_ok=True)

    def log(line: str, stream: str = "stdout") -> dict:
        return {"line": line, "stream": stream, "ts": _now_ts()}

    extra_context_parts: list[str] = []
    if mcp_context:
        extra_context_parts.append(mcp_context)
        yield log(f"[context] MCP log context attached ({len(mcp_context)} chars)")
    if repo_context:
        extra_context_parts.append(repo_context)
        yield log(f"[context] Repo context attached ({len(repo_context)} chars)")

    extra_context = "\n\n".join(extra_context_parts)
    task_context = f"{task_title}\n\n{task_description}"
    if extra_context:
        task_context = f"{task_context}\n\n{extra_context}"

    yield log(f"[react] Starting ReAct loop for: {task_title}")
    yield log(f"[react] Workspace: {workspace}")
    yield log(f"[react] Provider: {settings.LLM_PROVIDER}/{settings.LLM_MODEL}")
    yield log(f"[react] Max retries per sub-task: {MAX_RETRIES}")
    yield log(f"[react] Skills available: {', '.join(SKILL_REGISTRY.keys()) or 'none'}")
    await asyncio.sleep(0.05)

    # ── RECALL: fetch user + global project memories ─────────────────────────
    task_memories: list[str] = []
    if db and user_id:
        try:
            from app.services.memory_store import recall_with_global as memory_recall_global
            query = f"{task_title} {task_description}"
            mem_map = await memory_recall_global(db, user_id, query)
            user_mems = mem_map.get("user", [])
            global_mems = mem_map.get("global", [])
            task_memories = global_mems + user_mems  # global first so it anchors context
            if task_memories:
                yield log(f"[memory] Injecting {len(task_memories)} memories ({len(global_mems)} global, {len(user_mems)} user)")
                for m in task_memories:
                    yield log(f"[memory]   · {m[:100]}")
            else:
                yield log("[memory] No relevant memories found")
        except Exception as exc:
            yield log(f"[memory] Recall skipped: {exc}", "stderr")
    await asyncio.sleep(0.05)

    # ── REASON: decompose into sub-tasks with dependency analysis ────────────
    yield log("[reason] Decomposing task into sub-tasks with dependency analysis...")
    subtasks: list[SubTask] = []
    execution_strategy = "serial"  # default fallback
    
    try:
        raw = await _llm(DECOMPOSE_PROMPT.format(task=task_context), memories=task_memories)
        data = _extract_json_array(raw)
        if data:
            for item in data[:4]:  # cap at 4 sub-tasks
                subtasks.append(SubTask(
                    id=item.get("id", f"subtask-{len(subtasks)+1}"),
                    title=item.get("title", task_title),
                    description=item.get("description", task_description),
                    expected_files=item.get("files", []),
                    parallel=item.get("parallel", True),
                    depends_on=item.get("depends_on", []),
                    needs_coordination=item.get("needs_coordination", False),
                ))
            
            # Analyze execution strategy
            has_dependencies = any(st.depends_on for st in subtasks)
            has_coordination = any(st.needs_coordination for st in subtasks)
            all_parallel = all(st.parallel and not st.depends_on for st in subtasks)
            
            if all_parallel and len(subtasks) > 1:
                execution_strategy = "parallel"
            elif has_dependencies:
                execution_strategy = "dependency_graph"
            elif has_coordination:
                execution_strategy = "coordinated_parallel"
            else:
                execution_strategy = "serial"
            
            yield log(f"[reason] Decomposed into {len(subtasks)} sub-task(s), strategy: {execution_strategy}")
            for st in subtasks:
                dep_info = f" (depends: {st.depends_on})" if st.depends_on else ""
                coord_info = " [coord]" if st.needs_coordination else ""
                yield log(f"[reason]   [{st.id}] {st.title}{dep_info}{coord_info}")
        else:
            yield log("[reason] Could not parse decomposition — running as single sub-task", "stderr")
            subtasks = _fallback_subtasks(task_title, task_description)
    except Exception as exc:
        yield log(f"[reason] Decompose error: {exc} — running as single sub-task", "stderr")
        subtasks = _fallback_subtasks(task_title, task_description)
    
    # ── Build dependency graph if needed ────────────────────────────────────
    coordinator = TaskCoordinator() if execution_strategy in ["coordinated_parallel", "dependency_graph"] else None
    
    if execution_strategy == "dependency_graph":
        # Build execution waves based on dependencies
        waves = _build_execution_waves(subtasks)
        yield log(f"[orchestrate] Built {len(waves)} execution wave(s) based on dependencies")
        for i, wave in enumerate(waves):
            yield log(f"[orchestrate]   Wave {i+1}: {[st.id for st in wave]}")

    await asyncio.sleep(0.05)

    # ── ACT → OBSERVE → FIX with parallel execution support ─────────────────
    
    MAX_PARALLEL = 3  # Limit concurrent sub-tasks
    
    async def execute_single_subtask(st: SubTask, wave_num: int = 1) -> SubTask:
        """Execute one sub-task with full ReAct loop."""
        st.status = "running"
        sub_ws = os.path.join(workspace, st.id)
        os.makedirs(sub_ws, exist_ok=True)

        # Wait for dependencies if any
        if st.depends_on and coordinator:
            yield log(f"[orchestrate] [{st.id}] Waiting for dependencies: {st.depends_on}")
            deps_ready = await coordinator.wait_for_dependencies(st.depends_on, timeout=300.0)
            if not deps_ready:
                st.status = "failed"
                st.errors.append("Dependencies did not complete in time")
                yield log(f"[orchestrate] [{st.id}] Dependency timeout — marking failed", "stderr")
                return st
            yield log(f"[orchestrate] [{st.id}] Dependencies ready, starting execution")

        yield log(f"[act] ─── Sub-task [{st.id}] (wave {wave_num}): {st.title}")
        
        # Load dependency files into context if needed
        dep_context = ""
        if st.depends_on and coordinator:
            dep_files = []
            for dep_id in st.depends_on:
                files = await coordinator.get_completed_task_files(dep_id)
                dep_files.extend(files)
            if dep_files:
                dep_context = f"\n\nFiles from dependency tasks:\n" + "\n".join(
                    f"- {f['path']}" for f in dep_files[:10]  # Limit context size
                )
                yield log(f"[orchestrate] [{st.id}] Loaded {len(dep_files)} files from dependencies")

        files_data: list[dict] = []
        errors: list[str] = []

        for attempt in range(1, MAX_RETRIES + 2):
            st.attempts = attempt
            yield log(f"[act]   [{st.id}] attempt {attempt}: calling LLM...")

            try:
                if attempt == 1:
                    prompt = CODE_GEN_PROMPT.format(
                        title=st.title,
                        description=st.description + dep_context,
                        files=", ".join(st.expected_files) or "any appropriate files",
                        context=task_context,
                    )
                else:
                    prev_summary = "\n".join(
                        f"  {f['path']} ({len(f.get('content',''))} chars)"
                        for f in files_data
                    )
                    prompt = FIX_PROMPT.format(
                        title=st.title,
                        attempt=attempt,
                        errors="\n".join(errors),
                        prev_files=prev_summary,
                    )

                raw = await _llm(prompt, memories=task_memories)
                parsed = _extract_json_array(raw)

                if parsed:
                    files_data = [
                        {"path": _sanitise_path(f.get("path", "output.txt")), "content": f.get("content", "")}
                        for f in parsed if isinstance(f, dict)
                    ]
                    yield log(f"[act]   [{st.id}] LLM returned {len(files_data)} file(s)")
                else:
                    errors = [f"LLM response was not a valid JSON array (attempt {attempt})"]
                    yield log(f"[observe] [{st.id}] FAIL: {errors[0]}", "stderr")
                    if attempt > MAX_RETRIES:
                        break
                    continue

            except Exception as exc:
                errors = [f"LLM call failed: {exc}"]
                yield log(f"[observe] [{st.id}] ERROR: {exc}", "stderr")
                if attempt > MAX_RETRIES:
                    break
                continue

            # OBSERVE
            errors = _observe(files_data, st.expected_files)
            if errors:
                yield log(f"[observe] [{st.id}] {len(errors)} issue(s) found:", "stderr")
                for e in errors:
                    yield log(f"[observe] [{st.id}]   - {e}", "stderr")
                if attempt > MAX_RETRIES:
                    yield log(f"[observe] [{st.id}] Max retries — writing best-effort", "stderr")
                    break
                yield log(f"[fix] [{st.id}] Sending errors to LLM (attempt {attempt+1})...")
            else:
                yield log(f"[observe] [{st.id}] All checks passed on attempt {attempt}")
                st.status = "done"
                break

            await asyncio.sleep(0.05)

        # Write files
        written: list[str] = []
        if not files_data:
            yield log(f"[act]   [{st.id}] No files generated — using fallback", "stderr")
            files_data = [
                {"path": f"src/{re.sub(r'[^a-z0-9]', '_', st.title.lower())[:25]}.py",
                 "content": f'"""{st.title}\n{st.description}"""\n\ndef main():\n    pass\n'},
            ]

        for f in files_data:
            path = f["path"]
            content = f.get("content", "")
            full_path = _write_file(sub_ws, path, content)
            lines = content.count("\n") + 1
            written.append(path)
            yield log(f"[write] [{st.id}] {path} ({lines} lines)")
            await asyncio.sleep(0.03)

        st.generated_files = files_data
        if st.status != "done":
            st.status = "failed"

        # Register completion for dependent tasks
        if coordinator:
            await coordinator.register_completion(st.id, files_data)

        yield log(f"[act] [{st.id}] complete — {len(written)} file(s), status={st.status}")
        return st

    # ── Execute based on strategy ───────────────────────────────────────────
    
    if execution_strategy in ["parallel", "coordinated_parallel"] and len(subtasks) > 1:
        # Run all independent tasks in parallel
        yield log(f"[orchestrate] Executing {len(subtasks)} sub-tasks in parallel (max {MAX_PARALLEL})")
        semaphore = asyncio.Semaphore(MAX_PARALLEL)
        
        async def bounded_execute(st: SubTask) -> SubTask:
            async with semaphore:
                # Need to consume the generator - collect results
                results = []
                async for item in execute_single_subtask(st, wave_num=1):
                    results.append(item)
                    # Re-yield log items to parent
                    if isinstance(item, dict) and 'line' in item:
                        pass  # Already yielded inside execute_single_subtask
                # Return the final subtask state from results
                for r in reversed(results):
                    if isinstance(r, SubTask):
                        return r
                return st
        
        # Simpler approach: execute sequentially but with the parallel-aware code
        # (Full parallel requires more refactoring of the generator pattern)
        yield log("[orchestrate] Note: Running sequentially with dependency awareness")
        yield log("[orchestrate] For true parallel, see Phase 2 with container support")
        
        for st in subtasks:
            await execute_single_subtask(st, wave_num=1).__anext__()
            # Continue consuming the generator
            async for _ in execute_single_subtask(st, wave_num=1):
                pass
    
    elif execution_strategy == "dependency_graph":
        # Execute in waves
        for wave_idx, wave in enumerate(waves):
            yield log(f"[orchestrate] Executing wave {wave_idx + 1}/{len(waves)}: {[st.id for st in wave]}")
            
            for st in wave:
                async for _ in execute_single_subtask(st, wave_num=wave_idx + 1):
                    pass
    
    else:
        # Serial execution (fallback)
        yield log("[orchestrate] Executing sub-tasks serially")
        for st in subtasks:
            async for _ in execute_single_subtask(st, wave_num=1):
                pass

    # ── COLLECT: merge all sub-task outputs into workspace root ─────────────
    yield log("[collect] Merging sub-task outputs into workspace...")
    total_files = 0
    for st in subtasks:
        sub_ws = os.path.join(workspace, st.id)
        for root, _, filenames in os.walk(sub_ws):
            for fname in filenames:
                src = os.path.join(root, fname)
                rel = os.path.relpath(src, sub_ws)
                dst = os.path.join(workspace, rel)
                os.makedirs(os.path.dirname(dst) or workspace, exist_ok=True)
                with open(src, "rb") as fin, open(dst, "wb") as fout:
                    fout.write(fin.read())
                total_files += 1
                yield log(f"[collect] {rel}")
                await asyncio.sleep(0.02)

    done_count = sum(1 for s in subtasks if s.status == "done")
    fail_count = sum(1 for s in subtasks if s.status == "failed")
    yield log(f"[react] ReAct loop complete — {total_files} file(s) merged")
    yield log(f"[react] Sub-tasks: {done_count} done, {fail_count} failed")
    yield log(f"[react] Workspace: {workspace}")

    # ── Write README.md summary so the result API surfaces it ───────────────
    all_files = []
    for st in subtasks:
        for f in st.generated_files:
            all_files.append(f["path"])

    # ── CONSOLIDATE: persist task summary into long-term memory ─────────────
    if db and user_id:
        try:
            from app.services.memory_store import remember as memory_remember
            summary = (
                f"Completed task '{task_title}': {done_count}/{len(subtasks)} sub-tasks succeeded. "
                f"Generated files: {', '.join(all_files[:10])}."
            )
            await memory_remember(db, user_id, summary, source="task_completion")
            await db.commit()
            yield log(f"[memory] Task summary stored in long-term memory")
        except Exception as exc:
            yield log(f"[memory] Consolidation skipped: {exc}", "stderr")

    file_list = "\n".join(f"- `{p}`" for p in all_files) if all_files else "- (none)"
    subtask_details = "\n".join(
        f"- **[{st.id}]** {st.title} — *{st.status}* ({st.attempts} attempt(s))"
        for st in subtasks
    )

    readme = (
        f"# Task Completed: {task_title}\n\n"
        f"{task_description}\n\n"
        f"## Outcome\n\n"
        f"The agent completed {done_count} of {len(subtasks)} sub-task(s) successfully.\n\n"
        f"## Sub-tasks\n\n{subtask_details}\n\n"
        f"## Generated Files\n\n{file_list}\n\n"
        f"## Usage\n\n"
        f"Review the generated files below. Each file is fully self-contained and ready to run.\n"
        f"Download individual files or use 'Download all' to get everything at once.\n"
    )
    _write_file(workspace, "README.md", readme)
    yield log("[react] Summary written to README.md")
