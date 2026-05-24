"""
Workspace files API.
GET /api/v1/workspace/files?task_id=<uuid>  — list files for a task workspace
GET /api/v1/workspace/files/<path>          — read a single file (future)
"""
import os
from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user
from app.core.logger import get_logger

router = APIRouter(prefix="/workspace", tags=["workspace"])
logger = get_logger("workspace")

WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", "/tmp/devbuddy-workspaces")


def _scan_dir(path: str, prefix: str = "") -> list[dict]:
    """Recursively scan a directory and return a flat list of file entries."""
    entries: list[dict] = []
    try:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            rel  = f"{prefix}/{name}" if prefix else name
            if os.path.isdir(full):
                entries.append({"type": "dir", "path": rel, "name": name, "children": _scan_dir(full, rel)})
            else:
                size = os.path.getsize(full)
                entries.append({"type": "file", "path": rel, "name": name, "size": size})
    except PermissionError:
        pass
    return entries


@router.get("/files")
async def list_workspace_files(
    task_id: str | None = Query(None, description="Filter to a specific task workspace"),
    user: dict = Depends(get_current_user),
):
    if task_id:
        ws_path = os.path.join(WORKSPACE_ROOT, task_id)
    else:
        ws_path = WORKSPACE_ROOT

    if not os.path.exists(ws_path):
        return {"task_id": task_id, "root": ws_path, "files": [], "exists": False}

    files = _scan_dir(ws_path)
    logger.info("workspace_files_listed", task_id=task_id, count=len(files))
    return {"task_id": task_id, "root": ws_path, "files": files, "exists": True}


SKIP_PATTERNS = {
    "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
    "node_modules", ".DS_Store",
}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".egg-info"}


@router.get("/result/{task_id}")
async def get_task_result(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """Return all generated files with their content for a completed task."""
    ws_path = os.path.join(WORKSPACE_ROOT, task_id)
    if not os.path.exists(ws_path):
        return {"task_id": task_id, "exists": False, "summary": "", "files": []}

    result_files = []
    summary = ""

    for root, dirs, filenames in os.walk(ws_path):
        # Skip unwanted dirs in-place so os.walk doesn't descend into them
        dirs[:] = [d for d in dirs if d not in SKIP_PATTERNS]

        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS or fname in SKIP_PATTERNS:
                continue

            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, ws_path).replace("\\", "/")
            size = os.path.getsize(full)

            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except Exception:
                content = "<binary file>"

            # Capture summary.txt if present
            if fname in ("summary.txt", "SUMMARY.txt", "README.md") and not summary:
                summary = content
                continue  # Don't include summary file itself in artifact list

            result_files.append({"path": rel, "name": fname, "size": size, "content": content})

    # Build a summary if none was found
    if not summary and result_files:
        names = ", ".join(f["name"] for f in result_files[:5])
        summary = (
            f"Task completed successfully.\n\n"
            f"Generated {len(result_files)} file(s): {names}.\n\n"
            f"Review the artifacts below and download individual files or all at once."
        )

    # Sort: root files first, then subtask dirs
    result_files.sort(key=lambda f: (0 if "/" not in f["path"] else 1, f["path"]))

    logger.info("task_result_fetched", task_id=task_id, file_count=len(result_files))
    return {
        "task_id": task_id,
        "exists": True,
        "file_count": len(result_files),
        "summary": summary,
        "files": result_files,
    }
