"""
GitHub Connections API
=======================
Store GitHub tokens + repo URLs.
Clone repos into workspace on demand.
Agent executor reads cloned repo for context.
"""
import uuid
import os
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.logger import get_logger
from app.models.github_connection import GithubConnection

router = APIRouter(prefix="/github", tags=["github"])
logger = get_logger("github_connections")

REPOS_ROOT = os.environ.get("REPOS_ROOT", "/tmp/devbuddy-repos")


# ── Schemas ──────────────────────────────────────────────────────────────────

class GithubConnectionCreate(BaseModel):
    name: str
    repo_url: str          # https://github.com/org/repo  or  git@github.com:org/repo
    default_branch: str = "main"
    github_token: str = ""
    is_active: bool = True


class GithubConnectionUpdate(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    default_branch: str | None = None
    github_token: str | None = None
    is_active: bool | None = None


class GithubConnectionOut(BaseModel):
    id: str
    name: str
    repo_url: str
    default_branch: str
    has_token: bool
    is_active: bool
    clone_status: str | None
    cloned_at: str | None
    last_synced_at: str | None
    created_at: str

    class Config:
        from_attributes = True


def _to_out(c: GithubConnection) -> GithubConnectionOut:
    return GithubConnectionOut(
        id=str(c.id),
        name=c.name,
        repo_url=c.repo_url,
        default_branch=c.default_branch or "main",
        has_token=bool(c.github_token),
        is_active=c.is_active,
        clone_status=c.clone_status,
        cloned_at=c.cloned_at.isoformat() if c.cloned_at else None,
        last_synced_at=c.last_synced_at.isoformat() if c.last_synced_at else None,
        created_at=c.created_at.isoformat(),
    )


def _inject_token(url: str, token: str) -> str:
    """Inject PAT into https clone URL."""
    if token and url.startswith("https://github.com/"):
        return url.replace("https://github.com/", f"https://{token}@github.com/")
    return url


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/connections")
async def list_repos(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GithubConnection)
        .where(GithubConnection.tenant_id == uuid.UUID(user["tenant_id"]))
        .order_by(GithubConnection.created_at.desc())
    )
    return [_to_out(c) for c in result.scalars().all()]


@router.post("/connections", status_code=201)
async def add_repo(
    body: GithubConnectionCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conn = GithubConnection(
        tenant_id=uuid.UUID(user["tenant_id"]),
        name=body.name,
        repo_url=body.repo_url.rstrip("/"),
        default_branch=body.default_branch,
        github_token=body.github_token or None,
        is_active=body.is_active,
        clone_status="pending",
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    logger.info("github_connection_added", id=str(conn.id), repo=conn.repo_url)

    # Kick off background clone
    background_tasks.add_task(_clone_repo_bg, str(conn.id))
    return _to_out(conn)


@router.patch("/connections/{conn_id}")
async def update_repo(
    conn_id: str,
    body: GithubConnectionUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GithubConnection).where(GithubConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    if body.name is not None:
        conn.name = body.name
    if body.repo_url is not None:
        conn.repo_url = body.repo_url.rstrip("/")
    if body.default_branch is not None:
        conn.default_branch = body.default_branch
    if body.github_token is not None:
        conn.github_token = body.github_token or None
    if body.is_active is not None:
        conn.is_active = body.is_active
    conn.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(conn)
    return _to_out(conn)


@router.delete("/connections/{conn_id}", status_code=204)
async def delete_repo(
    conn_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GithubConnection).where(GithubConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    await db.delete(conn)
    await db.commit()


@router.post("/connections/{conn_id}/clone")
async def trigger_clone(
    conn_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger or re-trigger a clone/sync."""
    result = await db.execute(select(GithubConnection).where(GithubConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    conn.clone_status = "pending"
    await db.commit()
    background_tasks.add_task(_clone_repo_bg, conn_id)
    return {"queued": True}


@router.get("/connections/{conn_id}/tree")
async def repo_tree(
    conn_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List file tree of a cloned repo."""
    result = await db.execute(select(GithubConnection).where(GithubConnection.id == uuid.UUID(conn_id)))
    conn = result.scalar_one_or_none()
    if not conn or str(conn.tenant_id) != user["tenant_id"]:
        raise HTTPException(404, "Not found")
    if not conn.clone_path or not os.path.isdir(conn.clone_path):
        raise HTTPException(400, "Repo not cloned yet")

    entries = []
    for root, dirs, files in os.walk(conn.clone_path):
        # Skip .git
        dirs[:] = [d for d in dirs if d != ".git"]
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, conn.clone_path).replace("\\", "/")
            entries.append({"path": rel, "size": os.path.getsize(full)})
    return {"repo": conn.repo_url, "files": entries[:500]}


# ── Background clone ──────────────────────────────────────────────────────────

async def _clone_repo_bg(conn_id: str) -> None:
    """Run git clone / pull in a subprocess. Updates DB status."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GithubConnection).where(GithubConnection.id == uuid.UUID(conn_id)))
        conn = result.scalar_one_or_none()
        if not conn:
            return

        os.makedirs(REPOS_ROOT, exist_ok=True)
        repo_slug = conn.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        clone_dir = os.path.join(REPOS_ROOT, f"{conn_id[:8]}_{repo_slug}")
        conn.clone_path = clone_dir
        conn.clone_status = "cloning"
        await db.commit()

        try:
            clone_url = _inject_token(conn.repo_url, conn.github_token or "")

            if os.path.isdir(os.path.join(clone_dir, ".git")):
                # Already cloned — just pull
                proc = await asyncio.create_subprocess_exec(
                    "git", "-C", clone_dir, "pull", "--ff-only",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth=50", "--single-branch",
                    "--branch", conn.default_branch or "main",
                    clone_url, clone_dir,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )

            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode()[:500])

            conn.clone_status = "ready"
            conn.cloned_at = datetime.now(timezone.utc)
            conn.last_synced_at = datetime.now(timezone.utc)
            logger.info("repo_cloned", id=conn_id, path=clone_dir)
        except Exception as e:
            conn.clone_status = "failed"
            logger.error("repo_clone_failed", id=conn_id, error=str(e))

        await db.commit()


# ── Helper for agent executor ─────────────────────────────────────────────────

async def get_repo_context(tenant_id: str, db: AsyncSession, task_description: str = "") -> str:
    """
    Returns a compact file tree + key file snippets from active repos.
    Called by agent executor to give the LLM codebase awareness.
    """
    result = await db.execute(
        select(GithubConnection).where(
            GithubConnection.tenant_id == uuid.UUID(tenant_id),
            GithubConnection.is_active == True,
            GithubConnection.clone_status == "ready",
        )
    )
    repos = result.scalars().all()
    if not repos:
        return ""

    parts: list[str] = ["=== Connected Repositories ==="]
    for repo in repos:
        if not repo.clone_path or not os.path.isdir(repo.clone_path):
            continue
        parts.append(f"\n--- {repo.name} ({repo.repo_url}) ---")

        # Collect file list
        all_files: list[str] = []
        for root, dirs, files in os.walk(repo.clone_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, repo.clone_path).replace("\\", "/")
                all_files.append(rel)

        parts.append(f"Files ({len(all_files)}):")
        parts.extend(f"  {f}" for f in all_files[:50])
        if len(all_files) > 50:
            parts.append(f"  ... and {len(all_files)-50} more")

        # Read key files (README, main entry points)
        key_names = {"readme.md", "readme.rst", "main.py", "app.py", "index.ts", "index.js", "package.json", "pyproject.toml"}
        for rel in all_files:
            if rel.lower().split("/")[-1] in key_names:
                full = os.path.join(repo.clone_path, rel)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(3000)
                    parts.append(f"\n[{rel}]\n{content}\n")
                except Exception:
                    pass

    return "\n".join(parts) if len(parts) > 1 else ""
