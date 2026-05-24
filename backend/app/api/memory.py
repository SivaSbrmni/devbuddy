"""
Memory API
==========
REST endpoints for reading, adding, and deleting agent memories.

Privacy model:
- Every endpoint is scoped to the authenticated user only.
- No endpoint exposes any other user's data.
- /memory/project  — the user's own private project-level facts
- /memory/export   — full data export (GDPR portability)
- /memory          — all memory types for this user
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from sqlalchemy import select as sa_select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.memory import AgentMemory
from app.services.memory_store import (
    list_memories, remember, forget,
    remember_project, recall_full, export_all,
    MemorySource,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCreate(BaseModel):
    text: str
    source: Optional[str] = "manual"


@router.get("")
async def get_memories(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's stored memories (paginated)."""
    user_id = str(user["id"])
    items = await list_memories(db, user_id, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@router.post("")
async def add_memory(
    body: MemoryCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a memory for the current user."""
    user_id = str(user["id"])
    mem = await remember(db, user_id, body.text, source=body.source or "manual")
    await db.commit()
    return {"id": str(mem.id), "text": mem.text, "source": mem.source}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific memory by ID."""
    user_id = str(user["id"])
    count = await forget(db, user_id, memory_id=memory_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    await db.commit()
    return {"deleted": count}


@router.delete("")
async def clear_memories(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete ALL memories for the current user."""
    user_id = str(user["id"])
    count = await forget(db, user_id)
    await db.commit()
    return {"deleted": count}


# ── Per-user project memory (user's own private project facts) ───────────────

@router.get("/project")
async def get_project_memories(
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return this user's own project-level memories (tech stack, conventions, goals).
    These are private to this user and never shared with anyone.
    """
    user_id = str(user["id"])
    result = await db.execute(
        sa_select(AgentMemory)
        .where(AgentMemory.user_id == user_id)
        .where(AgentMemory.source == MemorySource.PROJECT)
        .order_by(AgentMemory.created_at.desc())
        .limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    items = [{"id": str(r.id), "text": r.text, "source": r.source, "created_at": r.created_at} for r in rows]
    return {"items": items, "count": len(items)}


@router.post("/project")
async def add_project_memory(
    body: MemoryCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a project-level fact for this user (e.g. tech stack, coding conventions).
    Stored privately under this user's ID only.
    """
    user_id = str(user["id"])
    mem = await remember_project(db, user_id, body.text)
    await db.commit()
    return {"id": str(mem.id), "text": mem.text, "source": mem.source}


# ── Data export (GDPR / portability) ─────────────────────────────────────────

@router.get("/export")
async def export_my_memories(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export ALL of this user's memories as JSON.
    The user owns their data entirely — no data has ever left their own DB.
    """
    user_id = str(user["id"])
    items = await export_all(db, user_id)
    return {
        "user_id": user_id,
        "exported_count": len(items),
        "privacy_note": "All memories are private to you and stored only in your own database.",
        "items": items,
    }
