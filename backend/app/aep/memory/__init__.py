"""AEP Memory System — Phase 4.

Long-term memory backed by pgvector for KNN similarity search, plus
Redis-backed working context for ephemeral per-execution scratch data.
"""

from app.aep.memory.context_engine import ContextEngine, get_context_engine
from app.aep.memory.service import MemoryService, get_memory_service

__all__ = [
    "ContextEngine",
    "get_context_engine",
    "MemoryService",
    "get_memory_service",
]
