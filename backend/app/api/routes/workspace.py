"""Workspace API routes — the virtual developer laptop."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.user import User
from app.workspace.manager import workspace_manager

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    project_id: str


class ExecCommandRequest(BaseModel):
    command: str
    timeout: int = 120
    cwd: str | None = None


class WriteFileRequest(BaseModel):
    path: str
    content: str


class EditFileRequest(BaseModel):
    path: str
    old: str
    new: str


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    user: User = Depends(get_current_user),
) -> dict:
    ws = await workspace_manager.create_workspace(body.project_id)
    return {
        "workspace_id": ws.workspace_id,
        "root_path": str(ws.root_path),
        "created_at": ws.created_at,
    }


@router.delete("/{workspace_id}", status_code=204, response_model=None)
async def destroy_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
) -> None:
    await workspace_manager.destroy_workspace(workspace_id)


@router.post("/{workspace_id}/exec")
async def exec_command(
    workspace_id: str,
    body: ExecCommandRequest,
    user: User = Depends(get_current_user),
) -> dict:
    from app.security.validator import workflow_validator

    validation = workflow_validator.validate_command(body.command)
    if not validation.allowed:
        raise HTTPException(403, validation.reason)

    result = await workspace_manager.exec_command(
        workspace_id, body.command, timeout=body.timeout, cwd=body.cwd
    )
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms,
    }


@router.get("/{workspace_id}/files")
async def list_files(
    workspace_id: str,
    path: str = ".",
    user: User = Depends(get_current_user),
) -> dict:
    files = await workspace_manager.list_files(workspace_id, path)
    return {"files": files}


@router.get("/{workspace_id}/files/read")
async def read_file(
    workspace_id: str,
    path: str,
    user: User = Depends(get_current_user),
) -> dict:
    try:
        content = await workspace_manager.read_file(workspace_id, path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {path}")
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/{workspace_id}/files/write")
async def write_file(
    workspace_id: str,
    body: WriteFileRequest,
    user: User = Depends(get_current_user),
) -> dict:
    from app.security.validator import workflow_validator

    validation = workflow_validator.validate_file_write(body.path, body.content)
    if not validation.allowed:
        raise HTTPException(403, validation.reason)

    await workspace_manager.write_file(workspace_id, body.path, body.content)
    return {"status": "written", "path": body.path}


@router.post("/{workspace_id}/files/edit")
async def edit_file(
    workspace_id: str,
    body: EditFileRequest,
    user: User = Depends(get_current_user),
) -> dict:
    success = await workspace_manager.edit_file(workspace_id, body.path, body.old, body.new)
    if not success:
        raise HTTPException(400, "Old string not found in file")
    return {"status": "edited", "path": body.path}


@router.delete("/{workspace_id}/files")
async def delete_file(
    workspace_id: str,
    path: str,
    user: User = Depends(get_current_user),
) -> dict:
    await workspace_manager.delete_file(workspace_id, path)
    return {"status": "deleted", "path": path}


@router.get("/{workspace_id}/history")
async def execution_history(
    workspace_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    history = workspace_manager.get_execution_history(workspace_id)
    return {
        "history": [
            {
                "command": h.command,
                "exit_code": h.exit_code,
                "duration_ms": h.duration_ms,
                "timestamp": h.timestamp,
            }
            for h in history
        ]
    }


@router.post("/{workspace_id}/git/clone")
async def clone_repo(
    workspace_id: str,
    repo_url: str,
    branch: str = "main",
    user: User = Depends(get_current_user),
) -> dict:
    result = await workspace_manager.clone_repo(workspace_id, repo_url, branch)
    return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}


@router.post("/{workspace_id}/git/commit-push")
async def commit_push(
    workspace_id: str,
    message: str,
    branch: str | None = None,
    user: User = Depends(get_current_user),
) -> dict:
    result = await workspace_manager.commit_and_push(workspace_id, message, branch)
    return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}
