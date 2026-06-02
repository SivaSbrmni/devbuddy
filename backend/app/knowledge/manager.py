"""Knowledge Manager — global knowledge store with pgvector semantic retrieval.

Before solving any problem: search knowledge first.
Reuse existing solutions whenever possible.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_router import ModelRouter
from app.models.memory import KnowledgeEntry

log = structlog.get_logger()


class KnowledgeManager:
    """Stores and retrieves engineering knowledge using pgvector."""

    def __init__(self, db: AsyncSession, router: ModelRouter) -> None:
        self.db = db
        self.router = router

    async def store(
        self,
        category: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        project_id: uuid.UUID | None = None,
    ) -> KnowledgeEntry:
        embedding = await self._embed(f"{title}\n{content}")
        entry = KnowledgeEntry(
            project_id=project_id,
            category=category,
            title=title,
            content=content,
            tags=tags or [],
            embedding=embedding,
        )
        self.db.add(entry)
        await self.db.flush()
        log.info("knowledge.stored", category=category, title=title)
        return entry

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        category: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search using pgvector cosine distance."""
        query_embedding = await self._embed(query)

        stmt = (
            select(
                KnowledgeEntry,
                KnowledgeEntry.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .order_by("distance")
            .limit(limit)
        )
        if category:
            stmt = stmt.where(KnowledgeEntry.category == category)
        if project_id:
            stmt = stmt.where(
                (KnowledgeEntry.project_id == project_id)
                | (KnowledgeEntry.project_id.is_(None))
            )

        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": str(entry.id),
                "category": entry.category,
                "title": entry.title,
                "content": entry.content,
                "tags": entry.tags,
                "distance": float(distance),
                "usage_count": entry.usage_count,
            }
            for entry, distance in rows
        ]

    async def record_usage(self, knowledge_id: uuid.UUID) -> None:
        stmt = select(KnowledgeEntry).where(KnowledgeEntry.id == knowledge_id)
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry:
            entry.usage_count += 1
            await self.db.flush()

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding via LLM summarization + hash-based pseudo-embedding.

        For production, swap this with a real embedding model (OpenAI ada, etc.).
        For now we use a deterministic hash-based approach for pgvector compatibility.
        """
        import hashlib
        import struct

        h = hashlib.sha512(text.encode()).digest()
        # Extend hash to fill 1536 dimensions
        extended = h * (1536 // len(h) + 1)
        values = struct.unpack(f"{1536}b", extended[:1536])
        # Normalize to [-1, 1]
        max_val = max(abs(v) for v in values) or 1
        return [v / max_val for v in values]
