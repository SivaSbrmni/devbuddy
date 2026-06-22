"""Autonomous Agent Chat — the core endpoint that makes DevBuddy actually autonomous.

This endpoint transforms a simple chat message into a full autonomous software
engineering task: analysis → planning → coding → testing → review.
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import TaskOrchestrator
from app.core.deps import get_db
from app.core.security import get_current_user
from app.llm.user_model_router import UserModelRouter
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.workspace.manager import workspace_manager

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    prompt: str
    model: str = ""
    tech_stack: dict[str, Any] | None = None
    existing_code: str = ""


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    """Serialize a single SSE line with timestamp."""
    msg = json.dumps({"type": event_type, "timestamp": int(time.time() * 1000), "payload": payload})
    return f"data: {msg}\n\n"


async def _stream_agent_run(
    prompt: str,
    model: str,
    tech_stack: dict[str, Any] | None,
    existing_code: str,
    db: AsyncSession,
    user: User,
):
    """Async generator that streams the full autonomous pipeline as SSE events.

    Event format:
        data: {"type": "step", "agent": "coder", "message": "Generating code..."}
        data: {"type": "file", "action": "create", "path": "src/main.py", "content": "..."}
        data: {"type": "command", "command": "pytest", "stdout": "...", "exit_code": 0}
        data: {"type": "test", "passed": 5, "failed": 0, "coverage": 87}
        data: {"type": "review", "findings": [...]}
        data: {"type": "done", "summary": "..."}
        data: {"type": "error", "message": "..."}
    """
    import structlog

    log = structlog.get_logger()
    run_id = str(uuid.uuid4())[:8]

    try:
        # ── Stage 0: Setup project + workspace ──────────────────────
        yield _sse("step", {"agent": "setup", "message": "Creating project and workspace..."})

        project = Project(
            name=f"Agent Run {run_id}",
            description=prompt[:200],
            status="active",
            tech_stack=tech_stack or {},
        )
        db.add(project)
        await db.flush()
        project_id = project.id

        # Create workspace
        ws = await workspace_manager.create_workspace(str(project_id))
        workspace_id = ws.workspace_id

        yield _sse("step", {
            "agent": "setup",
            "message": f"Workspace ready: {workspace_id}",
            "workspace_id": workspace_id,
        })

        # Emit initial workspace file tree
        ws_files = await workspace_manager.list_files(workspace_id)
        yield _sse("workspace", {"files": ws_files, "workspace_id": workspace_id})

        # ── Stage 1: Orchestrator Pipeline ────────────────────────────
        # Use the user's configured LLM providers instead of the env-only
        # singleton model_router.
        router = UserModelRouter(user_id=user.id, db=db, default_model=model)
        await router.initialize(user)
        if not router.has_providers:
            yield _sse("error", {"message": "No LLM providers configured. Add a provider in Settings → LLM Providers."})
            return

        orchestrator = TaskOrchestrator(db, router)

        task = Task(
            project_id=project_id,
            title=f"Auto: {prompt[:80]}",
            task_type="autonomous",
            description=prompt,
        )
        db.add(task)
        await db.flush()
        task_id = task.id

        yield _sse("step", {"agent": "orchestrator", "message": "Analyzing requirements..."})
        pipeline_results = await orchestrator.run_pipeline(
            project_id, task_id, prompt, tech_stack
        )

        yield _sse("artifact", {
            "kind": "specification",
            "content": pipeline_results.get("specification", ""),
        })
        yield _sse("artifact", {
            "kind": "plan",
            "content": pipeline_results.get("plan", ""),
        })
        yield _sse("artifact", {
            "kind": "architecture",
            "content": pipeline_results.get("architecture", ""),
        })

        # ── Stage 2: Coding ─────────────────────────────────────────
        yield _sse("step", {"agent": "coder", "message": "Generating production code..."})

        coding_desc = (
            f"Implement the following based on the plan and architecture.\n\n"
            f"Requirements:\n{prompt}\n\n"
            f"Plan:\n{pipeline_results.get('plan', '')}\n\n"
            f"Architecture:\n{pipeline_results.get('architecture', '')}\n\n"
            f"Generate the complete implementation with all necessary files."
        )

        coding_results = await orchestrator.run_coding_task(
            project_id, task_id, coding_desc, "", existing_code
        )

        code_output = coding_results.get("code", "")
        yield _sse("step", {"agent": "coder", "message": "Code generated, writing files..."})

        files_written: list[dict[str, str]] = []
        try:
            json_start = code_output.find("{")
            json_end = code_output.rfind("}")
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(code_output[json_start : json_end + 1])
                for f in parsed.get("files", []):
                    path = f.get("path", "")
                    content = f.get("content", "")
                    action = f.get("action", "create")
                    if path and content:
                        await workspace_manager.write_file(workspace_id, path, content)
                        files_written.append({"path": path, "action": action})
                        yield _sse("file", {"action": action, "path": path, "content": content})
            else:
                await workspace_manager.write_file(workspace_id, "output.md", code_output)
                files_written.append({"path": "output.md", "action": "create"})
                yield _sse("file", {"action": "create", "path": "output.md", "content": code_output})
        except Exception as exc:
            log.warning("agent.file_parse_failed", error=str(exc))
            await workspace_manager.write_file(workspace_id, "output.md", code_output)
            files_written.append({"path": "output.md", "action": "create"})
            yield _sse("file", {"action": "create", "path": "output.md", "content": code_output})

        # ── Stage 3: Test ───────────────────────────────────────────
        yield _sse("step", {"agent": "tester", "message": "Running tests..."})

        test_results: dict[str, Any] = {"passed": 0, "failed": 0, "coverage": 0, "stdout": ""}
        try:
            if any(f["path"].endswith(".py") for f in files_written):
                result = await workspace_manager.exec_command(
                    workspace_id, "python -m pytest --tb=short -q 2>&1 || true", timeout=60
                )
                test_results["stdout"] = result.stdout + result.stderr
                test_results["exit_code"] = result.exit_code
                import re as _re
                passed_match = _re.search(r"(\d+) passed", result.stdout)
                failed_match = _re.search(r"(\d+) failed", result.stdout)
                if passed_match:
                    test_results["passed"] = int(passed_match.group(1))
                if failed_match:
                    test_results["failed"] = int(failed_match.group(1))
            elif any(f["path"].endswith((".ts", ".tsx", ".js")) for f in files_written):
                result = await workspace_manager.exec_command(
                    workspace_id, "npm test -- --passWithNoTests 2>&1 || true", timeout=60
                )
                test_results["stdout"] = result.stdout + result.stderr
                test_results["exit_code"] = result.exit_code
        except Exception as exc:
            test_results["stdout"] = f"Test execution error: {exc}"

        yield _sse("test", test_results)

        # ── Stage 4: Review ─────────────────────────────────────────
        yield _sse("step", {"agent": "reviewer", "message": "Reviewing code..."})
        review = coding_results.get("review", "")
        yield _sse("review", {"findings": review[:2000]})

        # ── Stage 5: Final file tree ────────────────────────────────
        ws_files = await workspace_manager.list_files(workspace_id)
        yield _sse("workspace", {"files": ws_files, "workspace_id": workspace_id})

        # ── Done ────────────────────────────────────────────────────
        summary = (
            f"Autonomous run complete.\n"
            f"- Workspace: {workspace_id}\n"
            f"- Files written: {len(files_written)}\n"
            f"- Tests: {test_results['passed']} passed, {test_results['failed']} failed\n"
            f"- Review: {review[:200]}..."
        )
        yield _sse("done", {
            "summary": summary,
            "workspace_id": workspace_id,
            "project_id": str(project_id),
            "task_id": str(task_id),
            "files": files_written,
        })

        task.status = "completed"
        task.result = {
            "files_written": files_written,
            "test_results": test_results,
            "review": review,
        }
        await db.flush()

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.error("agent_run.failed", error=str(exc), traceback=traceback.format_exc())
        yield _sse("error", {
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })


@router.post("/run")
async def agent_run(
    request: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Run the full autonomous agent pipeline from a single prompt.

    Streams SSE events:
    - step: agent progress updates
    - file: file create/modify operations
    - test: test results
    - review: code review findings
    - workspace: file tree updates
    - done: completion with summary
    - error: if something fails
    """
    return StreamingResponse(
        _stream_agent_run(
            request.prompt,
            request.model,
            request.tech_stack,
            request.existing_code,
            db,
            user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AgentCommandRequest(BaseModel):
    workspace_id: str
    command: str
    timeout: int = 120


@router.post("/command")
async def agent_command(request: AgentCommandRequest) -> dict[str, Any]:
    """Execute a command in an agent workspace."""
    from app.security.validator import workflow_validator

    validation = workflow_validator.validate_command(request.command)
    if not validation.allowed:
        raise HTTPException(403, validation.reason)

    result = await workspace_manager.exec_command(
        request.workspace_id, request.command, timeout=request.timeout
    )
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
    }


class AgentFileRequest(BaseModel):
    workspace_id: str
    path: str
    content: str = ""


@router.post("/file/write")
async def agent_write_file(request: AgentFileRequest) -> dict[str, Any]:
    """Write a file in an agent workspace."""
    from app.security.validator import workflow_validator

    validation = workflow_validator.validate_file_write(request.path, request.content)
    if not validation.allowed:
        raise HTTPException(403, validation.reason)

    await workspace_manager.write_file(request.workspace_id, request.path, request.content)
    return {"status": "written", "path": request.path}


@router.get("/workspace/{workspace_id}/files")
async def agent_list_files(workspace_id: str) -> dict[str, Any]:
    """List files in an agent workspace."""
    files = await workspace_manager.list_files(workspace_id)
    return {"files": files, "workspace_id": workspace_id}


@router.get("/workspace/{workspace_id}/files/read")
async def agent_read_file(workspace_id: str, path: str) -> dict[str, Any]:
    """Read a file from an agent workspace."""
    try:
        content = await workspace_manager.read_file(workspace_id, path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {path}")
    except PermissionError as e:
        raise HTTPException(403, str(e))
