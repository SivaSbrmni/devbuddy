"""
Memory API
==========
REST endpoints for reading, adding, and deleting agent memories per user.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.memory_store import list_memories, remember, forget

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
