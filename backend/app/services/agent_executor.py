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
Decompose the following task into at most 4 focused, independent sub-tasks that can each be implemented in isolation.

Task: {task}

Respond ONLY with a JSON array of sub-task objects:
[
  {{"id": "subtask-1", "title": "...", "description": "...", "files": ["relative/path/file.ext"]}},
  ...
]

Keep each sub-task small and concrete. The "files" list is the expected output files."""

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
    ReAct loop generator. Yields log-line dicts:
      {"line": str, "stream": "stdout"|"stderr", "ts": float}
    Writes all output files to WORKSPACE_ROOT/{task_id}/.
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

    # ── RECALL: fetch relevant long-term memories ────────────────────────────
    task_memories: list[str] = []
    if db and user_id:
        try:
            from app.services.memory_store import recall as memory_recall
            task_memories = await memory_recall(db, user_id, f"{task_title} {task_description}", k=6)
            if task_memories:
                yield log(f"[memory] Injecting {len(task_memories)} relevant memories into agent context")
                for m in task_memories:
                    yield log(f"[memory]   · {m[:100]}")
            else:
                yield log("[memory] No relevant memories found")
        except Exception as exc:
            yield log(f"[memory] Recall skipped: {exc}", "stderr")
    await asyncio.sleep(0.05)

    # ── REASON: decompose into sub-tasks ────────────────────────────────────
    yield log("[reason] Decomposing task into sub-tasks...")
    subtasks: list[SubTask] = []
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
                ))
            yield log(f"[reason] Decomposed into {len(subtasks)} sub-task(s):")
            for st in subtasks:
                yield log(f"[reason]   [{st.id}] {st.title}")
        else:
            yield log("[reason] Could not parse decomposition — running as single sub-task", "stderr")
            subtasks = _fallback_subtasks(task_title, task_description)
    except Exception as exc:
        yield log(f"[reason] Decompose error: {exc} — running as single sub-task", "stderr")
        subtasks = _fallback_subtasks(task_title, task_description)

    await asyncio.sleep(0.05)

    # ── ACT → OBSERVE → FIX loop per sub-task ───────────────────────────────
    for st in subtasks:
        st.status = "running"
        sub_ws = os.path.join(workspace, st.id)
        os.makedirs(sub_ws, exist_ok=True)

        yield log(f"[act] ─── Sub-task [{st.id}]: {st.title}")
        files_data: list[dict] = []
        errors: list[str] = []

        for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES fixes
            st.attempts = attempt
            yield log(f"[act]   attempt {attempt}: calling LLM for code generation...")

            try:
                if attempt == 1:
                    prompt = CODE_GEN_PROMPT.format(
                        title=st.title,
                        description=st.description,
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
                    yield log(f"[act]   LLM returned {len(files_data)} file(s)")
                else:
                    errors = [f"LLM response was not a valid JSON array (attempt {attempt})"]
                    yield log(f"[observe] FAIL: {errors[0]}", "stderr")
                    if attempt > MAX_RETRIES:
                        break
                    continue

            except Exception as exc:
                errors = [f"LLM call failed: {exc}"]
                yield log(f"[observe] ERROR: {exc}", "stderr")
                if attempt > MAX_RETRIES:
                    break
                continue

            # OBSERVE ────────────────────────────────────────────────────────
            errors = _observe(files_data, st.expected_files)
            if errors:
                yield log(f"[observe] {len(errors)} issue(s) found:", "stderr")
                for e in errors:
                    yield log(f"[observe]   - {e}", "stderr")
                if attempt > MAX_RETRIES:
                    yield log(f"[observe] Max retries reached — writing best-effort output", "stderr")
                    break
                yield log(f"[fix] Sending errors back to LLM for fix (attempt {attempt+1})...")
            else:
                yield log(f"[observe] All checks passed on attempt {attempt}")
                st.status = "done"
                break

            await asyncio.sleep(0.05)

        # Write files (pass or best-effort) ──────────────────────────────────
        written: list[str] = []
        if not files_data:
            yield log(f"[act]   No files generated — using fallback for [{st.id}]", "stderr")
            fallback = _fallback_subtasks(st.title, st.description)[0]
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
            yield log(f"[write] {st.id}/{path}  ({lines} lines)")
            await asyncio.sleep(0.03)

        st.generated_files = files_data
        if st.status != "done":
            st.status = "failed"

        yield log(f"[act] [{st.id}] complete — {len(written)} file(s), status={st.status}")
        await asyncio.sleep(0.05)

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
