"""Context Engine — spec Part 7.

Indexes repositories and builds task context with semantic retrieval.
Integrates with the compression pipeline to fit within token budgets.

Memory types (spec Part 7):
  | Type | Storage | TTL | Purpose |
  | Working context | Redis | task lifetime | active state shared between agents |
  | Repository summary | Postgres + pgvector | indefinite | architecture/codebase overview |
  | Execution history | Postgres | 90 days | past runs, outputs, decisions |
  | Debugging patterns | Postgres + pgvector | indefinite | fix strategies per error type |
  | Code patterns | Postgres + pgvector | indefinite | style/architecture per repo |
  | Failure library | Postgres + pgvector | indefinite | known failure modes + resolutions |
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

log = structlog.get_logger()


@dataclass
class CompressedContext:
    """Context built for a specific task, compressed to fit token budget."""
    task_id: str
    content: str
    token_count: int
    sources: list[str] = field(default_factory=list)
    tokens_saved: dict = field(default_factory=dict)


@dataclass
class MemoryChunk:
    """A retrieved memory chunk from semantic search."""
    id: str
    content: str
    score: float
    memory_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Repository:
    """Repository reference for indexing."""
    owner: str
    repo: str
    url: str
    default_branch: str = "main"


@dataclass
class Task:
    """Task reference for context building."""
    id: str
    title: str
    description: str
    task_type: str = "planner"


@dataclass
class Execution:
    """Execution reference for summarization."""
    id: str
    task_id: str
    status: str
    output: str = ""


class ContextEngine:
    """Builds and manages context for autonomous agent execution.

    Indexes repositories (clone → AST parse → symbol extraction → file
    summaries → dependency graph → embeddings), compresses per-call via
    the compression pipeline, and caches embeddings (never re-embeds
    unchanged files).
    """

    def __init__(self) -> None:
        self._indexed_repos: set[str] = set()  # owner/repo
        self._file_cache: dict[str, dict[str, str]] = {}  # repo -> {path -> content_hash}

    async def index_repository(self, repo: Repository) -> None:
        """Index a repository for semantic search.

        Steps:
        1. Clone the repository (or use existing clone)
        2. Parse AST for each source file
        3. Extract symbols (functions, classes, imports)
        4. Generate file summaries
        5. Build dependency graph
        6. Generate embeddings for each file
        7. Store in aep_memory with namespace 'repo:{owner}/{repo}'

        In production, this runs as a background job. For now, we store
        a placeholder summary.
        """
        repo_key = f"{repo.owner}/{repo.repo}"
        log.info("context.indexing_start", repo=repo_key)

        # Check if already indexed
        if repo_key in self._indexed_repos:
            log.info("context.already_indexed", repo=repo_key)
            return

        # In production, this would clone and parse the repo
        # For now, store a placeholder summary in memory
        summary = f"Repository {repo_key}: {repo.url}\nDefault branch: {repo.default_branch}\nIndexing pending full implementation."

        # Store the summary in aep_memory
        try:
            from app.db.session import get_db
            from app.models.aep import AepMemory
            from sqlalchemy import select

            # Generate embedding (if LLM gateway is available)
            embedding = None
            if os.environ.get("GEMINI_API_KEY"):
                from app.llm.gateway import llm_gateway
                embeddings = await llm_gateway.embeddings([summary])
                if embeddings:
                    embedding = embeddings[0]

            # Store in database
            async for db in get_db():
                memory = AepMemory(
                    namespace=f"repo:{repo_key}",
                    entity_id="summary",
                    memory_type="repo_summary",
                    content=summary,
                    embedding=embedding,
                    metadata={"url": repo.url, "default_branch": repo.default_branch},
                )
                db.add(memory)
                await db.commit()

            self._indexed_repos.add(repo_key)
            log.info("context.indexed", repo=repo_key)

        except Exception as e:
            log.error("context.index_failed", repo=repo_key, error=str(e))

    async def build_task_context(self, task: Task, token_budget: int = 8000) -> CompressedContext:
        """Build compressed context for a task within a token budget.

        1. Retrieve relevant memories via semantic search
        2. Select chunks that fit within the token budget
        3. Compress via the compression pipeline
        4. Return the compressed context
        """
        from app.llm.compression import compress_payload

        # Semantic search for relevant context
        chunks = await self.semantic_search(
            query=f"{task.title} {task.description}",
            namespace="repo:",
            top_k=10,
        )

        # Build context string from chunks, respecting token budget
        # Rough estimate: 1 token ≈ 4 characters
        char_budget = token_budget * 4
        context_parts = []
        sources = []
        current_size = 0

        for chunk in chunks:
            chunk_size = len(chunk.content)
            if current_size + chunk_size > char_budget:
                # Drop the whole chunk — never truncate mid-thought (spec Part 3 [4])
                continue
            context_parts.append(chunk.content)
            sources.append(f"{chunk.memory_type}:{chunk.id}")
            current_size += chunk_size

        content = "\n\n".join(context_parts) if context_parts else f"Task: {task.title}\nDescription: {task.description}"

        # Compress the context
        compressed = compress_payload({
            "messages": [{"role": "system", "content": content}],
        }, task_id=task.id)

        tokens_saved = compressed.get("tokens_saved", {})

        return CompressedContext(
            task_id=task.id,
            content=content,
            token_count=current_size // 4,
            sources=sources,
            tokens_saved=tokens_saved,
        )

    async def semantic_search(self, query: str, namespace: str, top_k: int = 5) -> list[MemoryChunk]:
        """Search memory by semantic similarity.

        Uses pgvector cosine distance for retrieval.
        """
        try:
            from app.db.session import get_db
            from app.models.aep import AepMemory
            from sqlalchemy import select, text

            # Generate query embedding
            query_embedding = None
            if os.environ.get("GEMINI_API_KEY"):
                from app.llm.gateway import llm_gateway
                embeddings = await llm_gateway.embeddings([query])
                if embeddings:
                    query_embedding = embeddings[0]

            results = []
            async for db in get_db():
                if query_embedding:
                    # Use pgvector cosine distance
                    stmt = (
                        select(AepMemory)
                        .where(AepMemory.namespace.like(f"{namespace}%"))
                        .order_by(AepMemory.embedding.cosine_distance(query_embedding))
                        .limit(top_k)
                    )
                else:
                    # Fallback: text search
                    stmt = (
                        select(AepMemory)
                        .where(AepMemory.namespace.like(f"{namespace}%"))
                        .limit(top_k)
                    )

                rows = await db.execute(stmt)
                for row in rows.scalars():
                    results.append(MemoryChunk(
                        id=str(row.id),
                        content=row.content,
                        score=1.0,  # Score would come from pgvector
                        memory_type=row.memory_type,
                        metadata=row.metadata_ or {},
                    ))

            return results

        except Exception as e:
            log.error("context.search_failed", error=str(e))
            return []

    async def summarize_execution(self, execution: Execution) -> str:
        """Summarize an execution for storage in long-term memory."""
        from app.llm.gateway import llm_gateway

        if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
            return f"Execution {execution.id}: {execution.status}"

        try:
            response = await llm_gateway.chat(
                messages=[{
                    "role": "user",
                    "content": f"Summarize this execution:\nID: {execution.id}\nStatus: {execution.status}\nOutput: {execution.output[:2000]}",
                }],
                task_type="docs_summary",
                max_tokens=500,
            )
            return response.text
        except Exception as e:
            log.error("context.summarize_failed", error=str(e))
            return f"Execution {execution.id}: {execution.status}"

    async def update_index(self, repo: Repository, changed_files: list[str]) -> None:
        """Incrementally update the repository index for changed files.

        Only re-embeds changed files (never re-embeds unchanged files).
        """
        repo_key = f"{repo.owner}/{repo.repo}"
        log.info("context.update_index", repo=repo_key, changed_files=len(changed_files))

        # In production, this would:
        # 1. Fetch the new content of each changed file
        # 2. Generate new embeddings
        # 3. Update aep_memory records
        # 4. Update the dependency graph

        # For now, just log
        for file_path in changed_files:
            log.debug("context.reindex_file", repo=repo_key, file=file_path)


# Singleton
context_engine = ContextEngine()
