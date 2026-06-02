"""Memory & Knowledge API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.model_router import model_router
from app.knowledge.manager import KnowledgeManager
from app.memory.manager import MemoryManager
from app.schemas.project import (
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeSearchRequest,
    MemoryCreate,
    MemoryOut,
)

router = APIRouter(tags=["memory"])


# ── Project Memory ──────────────────────────────────────────────────
@router.post("/projects/{project_id}/memory", response_model=MemoryOut, status_code=201)
async def create_memory(
    project_id: uuid.UUID, body: MemoryCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    mgr = MemoryManager(db)
    mem = await mgr.store(project_id, body.category, body.title, body.content, body.metadata)
    return mem


@router.get("/projects/{project_id}/memory")
async def list_memories(
    project_id: uuid.UUID,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    mgr = MemoryManager(db)
    if category:
        memories = await mgr.recall(project_id, category)
        return {"memories": [
            {"id": str(m.id), "category": m.category, "title": m.title, "content": m.content}
            for m in memories
        ]}
    return await mgr.recall_all(project_id)


@router.get("/projects/{project_id}/memory/context")
async def get_memory_context(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    mgr = MemoryManager(db)
    context = await mgr.build_context_string(project_id)
    return {"context": context}


# ── Knowledge ───────────────────────────────────────────────────────
@router.post("/knowledge", response_model=KnowledgeOut, status_code=201)
async def create_knowledge(body: KnowledgeCreate, db: AsyncSession = Depends(get_db)) -> dict:
    mgr = KnowledgeManager(db, model_router)
    entry = await mgr.store(
        body.category, body.title, body.content, body.tags, body.project_id
    )
    return {
        "id": str(entry.id),
        "category": entry.category,
        "title": entry.title,
        "content": entry.content,
        "tags": entry.tags,
        "distance": None,
        "usage_count": entry.usage_count,
    }


@router.post("/knowledge/search", response_model=list[KnowledgeOut])
async def search_knowledge(
    body: KnowledgeSearchRequest, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    mgr = KnowledgeManager(db, model_router)
    return await mgr.search(body.query, limit=body.limit, category=body.category, project_id=body.project_id)
