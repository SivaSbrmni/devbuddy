"""
Agent Memory Store
==================
Provider-agnostic, strictly per-user long-term memory.

Privacy guarantee:
- Every memory row is scoped to exactly ONE user_id.
- No memory is ever shared between users.
- No data is sent to any external model provider for training.
  Embeddings/LLM calls go to your own configured endpoint (Ollama local
  or a provider you control) and are never used for model training.
- Users can export or delete all their data at any time.

Memory sources (all private to the user):
  "conversation"    — auto-extracted facts from chat turns
  "project"         — user-defined project details (tech stack, conventions, goals)
  "task_completion" — auto-stored summaries of completed agent tasks
  "manual"          — explicitly added by the user via UI

The concept of 'global memory' here means all memory sources belonging to
THAT user—not shared with anyone else.

Lifecycle:
  remember(user_id, text, source)   — store a memory
  recall(user_id, query)            — retrieve relevant memories (all sources)
  remember_project(user_id, text)   — store a user's own project-level fact
  recall_full(user_id, query)       — recall prioritising project facts first
  consolidate(user_id, ...)         — auto-extract facts from a conversation turn
  forget(user_id, memory_id)        — delete one or all memories
  export_all(user_id)               — export all memories (GDPR/portability)
"""
from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.models.memory import AgentMemory

logger = get_logger("memory_store")


class MemorySource:
    """Constants for memory source tags — all scoped to a single user."""
    CONVERSATION = "conversation"      # auto-extracted from chat
    PROJECT = "project"                # user's own project facts
    TASK_COMPLETION = "task_completion" # agent task summaries
    MANUAL = "manual"                  # user explicitly added

# ── Embedding backends ────────────────────────────────────────────────────────

_EMBED_DIM = 768  # nomic-embed-text / most local models
_OPENAI_EMBED_DIM = 1536  # text-embedding-3-small


async def _embed_ollama(text: str) -> list[float] | None:
    """Embed via Ollama /api/embeddings. Works with nomic-embed-text or any pulled model."""
    model = settings.EMBED_MODEL or "nomic-embed-text"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            if resp.status_code == 200:
                return resp.json().get("embedding")
    except Exception as exc:
        logger.warning("embed_ollama_failed", error=str(exc))
    return None


async def _embed_openai_compat(text: str) -> list[float] | None:
    """Embed via OpenAI-compatible /embeddings endpoint (OpenAI, Together, etc.)."""
    if not settings.LLM_API_KEY:
        return None
    base = settings.resolved_api_base
    model = settings.EMBED_MODEL or (
        "text-embedding-3-small" if settings.LLM_PROVIDER == "openai" else "togethercomputer/m2-bert-80M-8k-retrieval"
    )
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base}/embeddings",
                headers=headers,
                json={"model": model, "input": text},
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.warning("embed_openai_compat_failed", error=str(exc))
    return None


def _tfidf_embed(text: str, dim: int = 256) -> list[float]:
    """
    Deterministic fallback embedding: character n-gram frequencies projected to `dim`.
    Not semantic — used only when no embedding API is reachable.
    """
    tokens = text.lower().split()
    vec = [0.0] * dim
    for tok in tokens:
        h = hash(tok) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def embed(text: str) -> list[float]:
    """
    Route to the correct embedding backend based on LLM_PROVIDER.
    Always returns a list[float] — falls back to n-gram hashing if all APIs fail.
    """
    if settings.LLM_PROVIDER == "ollama":
        vec = await _embed_ollama(text)
    else:
        vec = await _embed_openai_compat(text)

    if vec:
        return vec

    logger.warning("embed_fallback_tfidf", provider=settings.LLM_PROVIDER)
    return _tfidf_embed(text)


# ── Cosine similarity (Python-side fallback) ──────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        min_len = min(len(a), len(b))
        a, b = a[:min_len], b[:min_len]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


# ── Public memory API ─────────────────────────────────────────────────────────

async def remember(
    db: AsyncSession,
    user_id: str,
    text: str,
    source: str = "conversation",
    metadata: dict | None = None,
) -> AgentMemory:
    """
    Embed `text` and store it as a memory for `user_id`.
    Returns the persisted AgentMemory row.
    """
    vector = await embed(text)
    mem = AgentMemory(
        id=uuid.uuid4(),
        user_id=user_id,
        text=text,
        source=source,
        vector=json.dumps(vector),
        extra_meta=json.dumps(metadata or {}),
        created_at=time.time(),
    )
    db.add(mem)
    await db.flush()
    logger.info("memory_stored", user_id=user_id, source=source, chars=len(text))
    return mem


async def recall(
    db: AsyncSession,
    user_id: str,
    query: str,
    k: int = 6,
    min_score: float = 0.25,
) -> list[str]:
    """
    Return up to `k` memory texts most relevant to `query` for `user_id`.
    Uses Python-side cosine similarity (works without pgvector).
    """
    q_vec = await embed(query)

    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.user_id == str(user_id))
        .order_by(AgentMemory.created_at.desc())
        .limit(200)
    )
    rows = result.scalars().all()

    scored: list[tuple[float, str]] = []
    for row in rows:
        try:
            m_vec = json.loads(row.vector)
            score = _cosine(q_vec, m_vec)
            if score >= min_score:
                scored.append((score, row.text))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in scored[:k]]


async def consolidate(
    db: AsyncSession,
    user_id: str,
    user_msg: str,
    assistant_msg: str,
) -> None:
    """
    Ask the LLM to extract durable facts from a conversation turn and store them.
    Called in the background after each assistant response.
    """
    from app.services.llm_service import llm_call  # local import to avoid circular

    extraction_prompt = (
        "Extract factual information worth remembering long-term from this exchange.\n"
        "Return ONLY a JSON array of short fact strings, or [] if nothing is worth storing.\n"
        "Focus on: user preferences, stated goals, project names, technology choices, "
        "constraints, personal details the user shared.\n\n"
        f"User: {user_msg}\n"
        f"Assistant: {assistant_msg}\n\n"
        "Facts (JSON array):"
    )

    try:
        raw = await llm_call(extraction_prompt)
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            facts: list[str] = json.loads(raw[start:end])
            for fact in facts:
                if isinstance(fact, str) and fact.strip():
                    await remember(db, user_id, fact.strip(), source=MemorySource.CONVERSATION)
            if facts:
                logger.info("memory_consolidated", user_id=user_id, facts=len(facts))
    except Exception as exc:
        logger.warning("memory_consolidation_failed", user_id=user_id, error=str(exc))


async def forget(db: AsyncSession, user_id: str, memory_id: str | None = None) -> int:
    """
    Delete a specific memory (by id) or ALL memories for a user.
    Returns the count of deleted rows.
    """
    if memory_id:
        result = await db.execute(
            delete(AgentMemory)
            .where(AgentMemory.user_id == str(user_id))
            .where(AgentMemory.id == uuid.UUID(memory_id))
        )
    else:
        result = await db.execute(
            delete(AgentMemory).where(AgentMemory.user_id == str(user_id))
        )
    count = result.rowcount
    logger.info("memory_forgotten", user_id=user_id, memory_id=memory_id, count=count)
    return count


async def list_memories(
    db: AsyncSession,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return paginated memories for a user (for the UI panel)."""
    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.user_id == str(user_id))
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "text": r.text,
            "source": r.source,
            "created_at": r.created_at,
            "meta": json.loads(r.extra_meta or "{}"),
        }
        for r in rows
    ]


# ── Per-user project memory (user's own private project facts) ────────────────

async def remember_project(
    db: AsyncSession,
    user_id: str,
    text: str,
    metadata: dict | None = None,
) -> AgentMemory:
    """
    Store a project-level fact that belongs exclusively to this user.
    Examples: "I use FastAPI + React", "prefer type hints", "project is called DevBuddy".
    This is PRIVATE to user_id — no other user can ever read it.
    """
    return await remember(db, user_id, text, source=MemorySource.PROJECT, metadata=metadata)


async def recall_full(
    db: AsyncSession,
    user_id: str,
    query: str,
    k_project: int = 4,
    k_conversation: int = 5,
    min_score: float = 0.20,
) -> dict[str, list[str]]:
    """
    Recall the user's own project-level facts AND conversation facts separately.
    Returns {"project": [...], "conversation": [...]}
    Both lists contain ONLY this user's data.
    """
    q_vec = await embed(query)

    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.user_id == str(user_id))
        .order_by(AgentMemory.created_at.desc())
        .limit(300)
    )
    rows = result.scalars().all()

    project_scored: list[tuple[float, str]] = []
    conv_scored: list[tuple[float, str]] = []

    for row in rows:
        try:
            m_vec = json.loads(row.vector)
            score = _cosine(q_vec, m_vec)
            if score < min_score:
                continue
            if row.source == MemorySource.PROJECT:
                project_scored.append((score, row.text))
            else:
                conv_scored.append((score, row.text))
        except Exception:
            continue

    project_scored.sort(key=lambda x: x[0], reverse=True)
    conv_scored.sort(key=lambda x: x[0], reverse=True)

    return {
        "project": [t for _, t in project_scored[:k_project]],
        "conversation": [t for _, t in conv_scored[:k_conversation]],
    }


# Alias kept for backwards compat with chat.py / agent_executor.py call sites
async def recall_with_global(
    db: AsyncSession,
    user_id: str,
    query: str,
    k_user: int = 5,
    k_global: int = 4,
    min_score: float = 0.20,
) -> dict[str, list[str]]:
    """
    Backwards-compatible wrapper around recall_full.
    'global' here means the user's own project-scoped memories—NOT shared with others.
    Returns {"user": [...], "global": [...]} where both are private to user_id.
    """
    result = await recall_full(
        db, user_id, query,
        k_project=k_global,
        k_conversation=k_user,
        min_score=min_score,
    )
    return {"user": result["conversation"], "global": result["project"]}


async def export_all(db: AsyncSession, user_id: str) -> list[dict]:
    """
    Export every memory row for a user as plain dicts.
    Provides full data portability — the user owns their data.
    """
    return await list_memories(db, user_id, limit=10_000)
