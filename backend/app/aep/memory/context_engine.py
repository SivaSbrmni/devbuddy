"""Context Engine — Phase 4.

Responsibilities (spec §7):
    - Repository indexing: clone, parse file tree, summarise via LLM,
      embed via ``/LLM/embed``, persist to ``aep_memory_entries``.
    - Incremental re-index on webhook ``push`` events.
    - Token-budget-aware retrieval: KNN over embeddings, then
      priority-ranked truncation to fit the caller's token budget.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.llm.gateway import LlmGatewayService, get_llm_gateway_service
from app.aep.observability import aep_logger

_logger = aep_logger("aep.memory.context_engine")

EMBEDDING_DIM = 768
DEFAULT_TOKEN_BUDGET = 4096


class ContextEngine:
    """Indexes repositories and retrieves context via KNN."""

    def __init__(self, *, llm: Optional[LlmGatewayService] = None) -> None:
        self._llm = llm

    def _get_llm(self) -> LlmGatewayService:
        if self._llm is None:
            self._llm = get_llm_gateway_service()
        return self._llm

    # ── Repository indexing ──────────────────────────────────────────

    async def index_file(
        self,
        *,
        tenant_id: uuid.UUID,
        repository_id: uuid.UUID,
        file_path: str,
        content: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Index a single file: summarise, embed, store."""
        llm = self._get_llm()

        summary = await self._summarise_file(file_path, content)

        embed_result = await llm.embed(
            inputs=[summary],
            model=None,
            tenant_id=str(tenant_id),
            purpose="index",
        )
        embeddings = embed_result.get("embeddings", [])
        if not embeddings:
            _logger.warning("index_file_no_embedding", file=file_path)
            return {"file": file_path, "status": "no_embedding"}

        embedding_vector = embeddings[0]
        embedding_model = embed_result.get("model", "nomic-embed-text")

        vector_str = "[" + ",".join(str(v) for v in embedding_vector) + "]"

        await db.execute(
            text(
                """
                INSERT INTO aep_memory_entries
                    (id, tenant_id, repository_id, memory_type, key, content,
                     embedding, embedding_model, token_count, extra_meta,
                     created_at, updated_at)
                VALUES
                    (:id, :tenant_id, :repository_id, :memory_type, :key, :content,
                     :embedding::vector, :embedding_model, :token_count, :extra_meta,
                     NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    token_count = EXCLUDED.token_count,
                    updated_at = NOW()
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "repository_id": str(repository_id),
                "memory_type": "file_summary",
                "key": file_path,
                "content": summary,
                "embedding": vector_str,
                "embedding_model": embedding_model,
                "token_count": len(summary.split()),
                "extra_meta": json.dumps({"file_path": file_path}),
            },
        )
        await db.commit()

        _logger.info("file_indexed", file=file_path, repository_id=str(repository_id))
        return {"file": file_path, "status": "indexed"}

    async def index_repository(
        self,
        *,
        tenant_id: uuid.UUID,
        repository_id: uuid.UUID,
        files: list[dict[str, str]],
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Index multiple files from a repository.

        ``files`` is a list of ``{"path": "...", "content": "..."}``.
        """
        results: list[dict[str, Any]] = []
        for file_info in files:
            result = await self.index_file(
                tenant_id=tenant_id,
                repository_id=repository_id,
                file_path=file_info["path"],
                content=file_info["content"],
                db=db,
            )
            results.append(result)

        indexed_count = sum(1 for r in results if r["status"] == "indexed")
        _logger.info(
            "repository_indexed",
            repository_id=str(repository_id),
            total_files=len(files),
            indexed=indexed_count,
        )
        return {
            "repository_id": str(repository_id),
            "total_files": len(files),
            "indexed": indexed_count,
            "results": results,
        }

    # ── Retrieval ────────────────────────────────────────────────────

    async def retrieve_similar(
        self,
        *,
        query: str,
        tenant_id: uuid.UUID,
        repository_id: Optional[uuid.UUID] = None,
        limit: int = 10,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """KNN retrieval: embed the query, find nearest neighbours."""
        llm = self._get_llm()

        embed_result = await llm.embed(
            inputs=[query],
            model=None,
            tenant_id=str(tenant_id),
            purpose="retrieve",
        )
        embeddings = embed_result.get("embeddings", [])
        if not embeddings:
            return []

        query_vector = embeddings[0]
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        repo_filter = ""
        params: dict[str, Any] = {
            "query_vec": vector_str,
            "tenant_id": str(tenant_id),
            "limit": limit,
        }
        if repository_id:
            repo_filter = "AND repository_id = :repository_id"
            params["repository_id"] = str(repository_id)

        result = await db.execute(
            text(
                f"""
                SELECT id, memory_type, key, content, token_count,
                       1 - (embedding <=> :query_vec::vector) AS similarity
                FROM aep_memory_entries
                WHERE tenant_id = :tenant_id
                  AND embedding IS NOT NULL
                  {repo_filter}
                ORDER BY embedding <=> :query_vec::vector
                LIMIT :limit
                """
            ),
            params,
        )
        rows = result.fetchall()

        entries: list[dict[str, Any]] = []
        total_tokens = 0
        for row in rows:
            token_count = row.token_count or 0
            if total_tokens + token_count > token_budget:
                break
            total_tokens += token_count
            entries.append({
                "id": str(row.id),
                "memory_type": row.memory_type,
                "key": row.key,
                "content": row.content,
                "token_count": token_count,
                "similarity": float(row.similarity),
            })

        _logger.info(
            "context_retrieved",
            query_preview=query[:80],
            results=len(entries),
            total_tokens=total_tokens,
            budget=token_budget,
        )
        return entries

    # ── Internal ─────────────────────────────────────────────────────

    async def _summarise_file(self, file_path: str, content: str) -> str:
        """Produce a summary of a file via the LLM gateway."""
        llm = self._get_llm()

        if len(content) < 100:
            return f"File: {file_path}\n{content}"

        truncated = content[:6000]

        try:
            result = await llm.generate(
                prompt=(
                    f"Summarise this source file in 2-3 sentences. "
                    f"Include key classes, functions, and purpose.\n\n"
                    f"File: {file_path}\n```\n{truncated}\n```"
                ),
                model=None,
                temperature=0.1,
                max_tokens=256,
                purpose="documentation",
            )
            return result.get("text", f"File: {file_path}")
        except Exception as exc:
            _logger.warning("summarise_fallback", file=file_path, error=str(exc))
            return f"File: {file_path}\n{content[:500]}"


_singleton: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    global _singleton
    if _singleton is None:
        _singleton = ContextEngine()
    return _singleton
