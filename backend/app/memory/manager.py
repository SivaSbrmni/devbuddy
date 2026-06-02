"""Project Memory Manager — permanent per-project memory that survives restarts.

Stores vision, goals, requirements, architecture, constraints, decisions,
coding standards, security standards, deployment standards, conversations,
milestones, lessons learned.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ProjectMemory

log = structlog.get_logger()


class MemoryManager:
    """CRUD + retrieval for project memory."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def store(
        self,
        project_id: uuid.UUID,
        category: str,
        title: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectMemory:
        mem = ProjectMemory(
            project_id=project_id,
            category=category,
            title=title,
            content=content,
            metadata_=metadata or {},
        )
        self.db.add(mem)
        await self.db.flush()
        log.info("memory.stored", project_id=str(project_id), category=category, title=title)
        return mem

    async def recall(
        self,
        project_id: uuid.UUID,
        category: str | None = None,
    ) -> list[ProjectMemory]:
        stmt = select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        if category:
            stmt = stmt.where(ProjectMemory.category == category)
        stmt = stmt.order_by(ProjectMemory.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def recall_all(self, project_id: uuid.UUID) -> dict[str, list[dict[str, Any]]]:
        memories = await self.recall(project_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for mem in memories:
            grouped.setdefault(mem.category, []).append({
                "id": str(mem.id),
                "title": mem.title,
                "content": mem.content,
                "metadata": mem.metadata_,
                "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
            })
        return grouped

    async def update(self, memory_id: uuid.UUID, content: str) -> ProjectMemory | None:
        stmt = select(ProjectMemory).where(ProjectMemory.id == memory_id)
        result = await self.db.execute(stmt)
        mem = result.scalar_one_or_none()
        if mem:
            mem.content = content
            await self.db.flush()
        return mem

    async def delete(self, memory_id: uuid.UUID) -> bool:
        stmt = select(ProjectMemory).where(ProjectMemory.id == memory_id)
        result = await self.db.execute(stmt)
        mem = result.scalar_one_or_none()
        if mem:
            await self.db.delete(mem)
            await self.db.flush()
            return True
        return False

    async def build_context_string(self, project_id: uuid.UUID) -> str:
        """Build a single context string from all project memories for LLM prompts."""
        all_memories = await self.recall_all(project_id)
        parts: list[str] = []
        for category, items in all_memories.items():
            parts.append(f"## {category.replace('_', ' ').title()}")
            for item in items:
                parts.append(f"### {item['title']}")
                parts.append(item["content"])
                parts.append("")
        return "\n".join(parts)
