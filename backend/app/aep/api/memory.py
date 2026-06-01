"""AEP Memory API — Phase 4.

Routes:
    POST  /api/v1/aep/memory/index         — index repository files
    POST  /api/v1/aep/memory/search         — KNN similarity search
    POST  /api/v1/aep/memory/store          — store a memory entry
    GET   /api/v1/aep/memory                — list memory entries
    POST  /api/v1/aep/memory/failure        — store a failure pattern
    GET   /api/v1/aep/memory/failure/{sig}  — look up fix strategy
    POST  /api/v1/aep/memory/working        — store working context
    GET   /api/v1/aep/memory/working/{eid}  — recall working context
    DELETE /api/v1/aep/memory/working/{eid} — delete working context

All routes gated behind ``memory_system_enabled`` flag.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.feature_flags import get_feature_flag_service
from app.aep.memory.service import get_memory_service
from app.core.security import get_current_user
from app.core.database import get_db

router = APIRouter(
    prefix="/aep/memory",
    tags=["aep-memory"],
)


def _check_memory_enabled() -> None:
    fs = get_feature_flag_service()
    if not fs.is_enabled("memory_system_enabled"):
        raise HTTPException(
            status_code=503,
            detail="Memory system is disabled. Enable the 'memory_system_enabled' flag.",
        )


def _tenant_id(user: Any) -> uuid.UUID:
    payload = getattr(user, "payload", None) or {}
    tid = payload.get("tenant_id") or payload.get("sub")
    if not tid:
        raise HTTPException(status_code=400, detail="tenant_id not found in token")
    return uuid.UUID(tid) if isinstance(tid, str) else tid


# ── Schemas ──────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    repository_id: uuid.UUID
    files: list[dict[str, str]] = Field(
        ..., description="List of {path, content} dicts"
    )


class SearchRequest(BaseModel):
    query: str
    repository_id: Optional[uuid.UUID] = None
    limit: int = Field(default=10, ge=1, le=100)
    token_budget: int = Field(default=4096, ge=100, le=128000)


class StoreMemoryRequest(BaseModel):
    memory_type: str
    key: str
    content: str
    repository_id: Optional[uuid.UUID] = None
    extra_meta: Optional[dict[str, Any]] = None
    embed: bool = False


class StoreFailureRequest(BaseModel):
    error_signature: str
    fix_strategy: str
    repository_id: Optional[uuid.UUID] = None
    context: dict[str, Any] = Field(default_factory=dict)


class WorkingContextRequest(BaseModel):
    execution_id: uuid.UUID
    data: dict[str, Any]


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/index")
async def index_repository(
    body: IndexRequest,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    return await svc.index_repository(
        tenant_id=tid,
        repository_id=body.repository_id,
        files=body.files,
        db=db,
    )


@router.post("/search")
async def search_similar(
    body: SearchRequest,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    return await svc.retrieve_similar(
        query=body.query,
        tenant_id=tid,
        repository_id=body.repository_id,
        limit=body.limit,
        token_budget=body.token_budget,
        db=db,
    )


@router.post("/store")
async def store_memory(
    body: StoreMemoryRequest,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    return await svc.store_memory(
        tenant_id=tid,
        memory_type=body.memory_type,
        key=body.key,
        content=body.content,
        repository_id=body.repository_id,
        extra_meta=body.extra_meta,
        embed=body.embed,
        db=db,
    )


@router.get("")
async def list_memories(
    memory_type: Optional[str] = None,
    key_prefix: Optional[str] = None,
    limit: int = 50,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    return await svc.search_memories(
        tenant_id=tid,
        memory_type=memory_type,
        key_prefix=key_prefix,
        limit=limit,
        db=db,
    )


@router.post("/failure")
async def store_failure(
    body: StoreFailureRequest,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    return await svc.store_failure_pattern(
        tenant_id=tid,
        repository_id=body.repository_id,
        error_signature=body.error_signature,
        fix_strategy=body.fix_strategy,
        context=body.context,
        db=db,
    )


@router.get("/failure/{signature}")
async def lookup_failure(
    signature: str,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    result = await svc.lookup_fix_strategy(
        error_signature=signature,
        tenant_id=tid,
        db=db,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No fix strategy found")
    return result


@router.post("/working")
async def store_working(
    body: WorkingContextRequest,
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    stored = await svc.store_working_context(tid, body.execution_id, body.data)
    return {"stored": stored, "execution_id": str(body.execution_id)}


@router.get("/working/{execution_id}")
async def recall_working(
    execution_id: uuid.UUID,
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    data = await svc.recall_working_context(tid, execution_id)
    return {"execution_id": str(execution_id), "data": data}


@router.delete("/working/{execution_id}")
async def delete_working(
    execution_id: uuid.UUID,
    user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    _check_memory_enabled()
    svc = get_memory_service()
    tid = _tenant_id(user)
    deleted = await svc.delete_working_context(tid, execution_id)
    return {"deleted": deleted, "execution_id": str(execution_id)}
