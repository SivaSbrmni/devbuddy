"""Memory Service — Phase 4.

Typed methods per spec §7:
    - ``store_working_context`` / ``recall_working_context`` — Redis-backed
      ephemeral per-execution scratch (key: ``aep:{tenant_id}:working:{execution_id}``).
    - ``index_repository`` — delegates to :class:`ContextEngine`.
    - ``retrieve_similar`` — KNN over pgvector embeddings.
    - ``store_failure_pattern`` / ``lookup_fix_strategy`` — durable
      Postgres entries for learning from past failures.
    - ``store_memory`` / ``search_memories`` — general-purpose memory CRUD.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.memory.context_engine import ContextEngine, get_context_engine
from app.aep.models import AepMemoryEntry
from app.aep.observability import aep_logger

_logger = aep_logger("aep.memory.service")


class RedisWorkingContext:
    """Redis-backed working context for ephemeral per-execution data.

    Key pattern: ``aep:{tenant_id}:working:{execution_id}``
    TTL: 24 hours (configurable via ``AEP_WORKING_CONTEXT_TTL``).

    Falls back gracefully when Redis is unavailable — logs a warning
    and returns empty dicts rather than raising.
    """

    def __init__(self) -> None:
        self._redis = None
        self._ttl = int(os.environ.get("AEP_WORKING_CONTEXT_TTL", "86400"))

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            url = os.environ.get("AEP_REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            _logger.info("redis_connected", url=url)
            return self._redis
        except Exception as exc:
            _logger.warning("redis_unavailable", error=str(exc))
            self._redis = None
            return None

    def _key(self, tenant_id: uuid.UUID, execution_id: uuid.UUID) -> str:
        return f"aep:{tenant_id}:working:{execution_id}"

    async def store(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
        data: dict[str, Any],
    ) -> bool:
        r = await self._get_redis()
        if r is None:
            return False
        try:
            key = self._key(tenant_id, execution_id)
            await r.set(key, json.dumps(data), ex=self._ttl)
            return True
        except Exception as exc:
            _logger.warning("redis_store_error", error=str(exc))
            return False

    async def recall(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> dict[str, Any]:
        r = await self._get_redis()
        if r is None:
            return {}
        try:
            key = self._key(tenant_id, execution_id)
            raw = await r.get(key)
            return json.loads(raw) if raw else {}
        except Exception as exc:
            _logger.warning("redis_recall_error", error=str(exc))
            return {}

    async def delete(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> bool:
        r = await self._get_redis()
        if r is None:
            return False
        try:
            key = self._key(tenant_id, execution_id)
            await r.delete(key)
            return True
        except Exception as exc:
            _logger.warning("redis_delete_error", error=str(exc))
            return False


class MemoryService:
    """High-level memory operations for the AEP execution engine."""

    def __init__(
        self,
        *,
        context_engine: Optional[ContextEngine] = None,
        working_ctx: Optional[RedisWorkingContext] = None,
    ) -> None:
        self._ctx = context_engine
        self._working = working_ctx or RedisWorkingContext()

    def _get_context_engine(self) -> ContextEngine:
        if self._ctx is None:
            self._ctx = get_context_engine()
        return self._ctx

    # ── Working context (Redis) ──────────────────────────────────────

    async def store_working_context(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
        data: dict[str, Any],
    ) -> bool:
        return await self._working.store(tenant_id, execution_id, data)

    async def recall_working_context(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> dict[str, Any]:
        return await self._working.recall(tenant_id, execution_id)

    async def delete_working_context(
        self,
        tenant_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> bool:
        return await self._working.delete(tenant_id, execution_id)

    # ── Repository indexing (pgvector) ───────────────────────────────

    async def index_repository(
        self,
        *,
        tenant_id: uuid.UUID,
        repository_id: uuid.UUID,
        files: list[dict[str, str]],
        db: AsyncSession,
    ) -> dict[str, Any]:
        engine = self._get_context_engine()
        return await engine.index_repository(
            tenant_id=tenant_id,
            repository_id=repository_id,
            files=files,
            db=db,
        )

    # ── KNN retrieval ────────────────────────────────────────────────

    async def retrieve_similar(
        self,
        *,
        query: str,
        tenant_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None,
        limit: int = 10,
        token_budget: int = 4096,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        engine = self._get_context_engine()
        return await engine.retrieve_similar(
            query=query,
            tenant_id=tenant_id,
            repository_id=repository_id,
            limit=limit,
            token_budget=token_budget,
            db=db,
        )

    # ── Failure patterns (durable Postgres) ──────────────────────────

    async def store_failure_pattern(
        self,
        *,
        tenant_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None,
        error_signature: str,
        fix_strategy: str,
        context: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Store a failure pattern and its fix for future lookup."""
        entry = AepMemoryEntry(
            tenant_id=tenant_id,
            repository_id=repository_id,
            memory_type="failure_pattern",
            key=error_signature,
            content=fix_strategy,
            extra_meta=context,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        _logger.info(
            "failure_pattern_stored",
            signature=error_signature[:80],
            tenant_id=str(tenant_id),
        )
        return {
            "id": str(entry.id),
            "memory_type": "failure_pattern",
            "key": error_signature,
            "content": fix_strategy,
        }

    async def lookup_fix_strategy(
        self,
        *,
        error_signature: str,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[dict[str, Any]]:
        """Look up a known fix strategy for an error signature."""
        result = await db.execute(
            select(AepMemoryEntry).where(
                AepMemoryEntry.tenant_id == tenant_id,
                AepMemoryEntry.memory_type == "failure_pattern",
                AepMemoryEntry.key == error_signature,
            ).order_by(AepMemoryEntry.created_at.desc()).limit(1)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            return None
        return {
            "id": str(entry.id),
            "fix_strategy": entry.content,
            "context": entry.extra_meta,
        }

    # ── General-purpose memory CRUD ──────────────────────────────────

    async def store_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: str,
        key: str,
        content: str,
        repository_id: Optional[uuid.UUID] = None,
        extra_meta: Optional[dict[str, Any]] = None,
        embed: bool = False,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Store a memory entry, optionally embedding the content."""
        entry = AepMemoryEntry(
            tenant_id=tenant_id,
            repository_id=repository_id,
            memory_type=memory_type,
            key=key,
            content=content,
            token_count=len(content.split()),
            extra_meta=extra_meta or {},
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        if embed:
            try:
                engine = self._get_context_engine()
                llm = engine._get_llm()
                embed_result = await llm.embed(
                    inputs=[content],
                    model=None,
                    tenant_id=str(tenant_id),
                    purpose="store",
                )
                embeddings = embed_result.get("embeddings", [])
                if embeddings:
                    vector_str = "[" + ",".join(str(v) for v in embeddings[0]) + "]"
                    await db.execute(
                        text(
                            "UPDATE aep_memory_entries "
                            "SET embedding = :vec::vector, "
                            "    embedding_model = :model "
                            "WHERE id = :id"
                        ),
                        {
                            "vec": vector_str,
                            "model": embed_result.get("model", "nomic-embed-text"),
                            "id": str(entry.id),
                        },
                    )
                    await db.commit()
            except Exception as exc:
                _logger.warning("embed_on_store_failed", error=str(exc))

        return {
            "id": str(entry.id),
            "memory_type": memory_type,
            "key": key,
            "content": content,
        }

    async def search_memories(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: Optional[str] = None,
        key_prefix: Optional[str] = None,
        limit: int = 50,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Search memory entries by type and/or key prefix."""
        query = select(AepMemoryEntry).where(
            AepMemoryEntry.tenant_id == tenant_id
        )
        if memory_type:
            query = query.where(AepMemoryEntry.memory_type == memory_type)
        if key_prefix:
            query = query.where(AepMemoryEntry.key.like(f"{key_prefix}%"))

        query = query.order_by(AepMemoryEntry.created_at.desc()).limit(limit)
        result = await db.execute(query)
        entries = result.scalars().all()

        return [
            {
                "id": str(e.id),
                "memory_type": e.memory_type,
                "key": e.key,
                "content": e.content,
                "token_count": e.token_count,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]


_singleton: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    global _singleton
    if _singleton is None:
        _singleton = MemoryService()
    return _singleton
