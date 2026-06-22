"""Local embedding provider (Priority 4).

Path A: 768-dim output to match the existing `aep_memory.embedding` column.
No schema change, no re-embedding migration needed.

This implementation uses a deterministic, lightweight embedding function so it
works without additional native dependencies. In production, replace the
`_embed_text` method with an ONNX Runtime inference session (e.g. a quantized
`nomic-embed-text` or `bge-base` variant) loaded once at startup.
"""

from __future__ import annotations

import hashlib
import math
from typing import AsyncIterator

import structlog

from app.llm.providers.base import BaseProvider, NormalizedResponse, ProviderConfig

log = structlog.get_logger()

REQUIRED_DIMENSIONS = 768  # Must match aep_memory.embedding column


def _embed_text(text: str, dimensions: int = REQUIRED_DIMENSIONS) -> list[float]:
    """Deterministic, lightweight local embedding.

    This is a stand-in for ONNX inference. It is stable, reproducible, and
    dimension-compatible, but not semantically meaningful. For real semantic
    retrieval, load a quantized embedding model via ONNX Runtime here.
    """
    # Use a hash of the text as a fixed seed for reproducibility
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = _DeterministicRNG(seed)
    # Generate a deterministic unit-ish vector with a small bias from the text
    values = [rng.gaussian() + 0.01 * (i % 7) for i in range(dimensions)]
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        return [0.0] * dimensions
    return [v / norm for v in values]


class _DeterministicRNG:
    """Simple deterministic random number generator for reproducibility."""

    def __init__(self, seed: int) -> None:
        self._state = seed % (2**31)

    def _next(self) -> int:
        self._state = (1103515245 * self._state + 12345) % (2**31)
        return self._state

    def gaussian(self) -> float:
        # Box-Muller using deterministic samples
        u1 = self._next() / (2**31)
        u2 = self._next() / (2**31)
        if u1 <= 0:
            u1 = 0.0001
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


class LocalEmbeddingProvider(BaseProvider):
    """In-process local embedding provider with no network call.

    Dimensions are asserted at startup against the aep_memory column.
    The gateway skips quota-ledger checks for `is_local` providers.
    """

    name = "local-onnx"
    dimensions = REQUIRED_DIMENSIONS

    def __init__(self, model: str = "local-onnx") -> None:
        config = ProviderConfig(
            name=self.name,
            models=[model],
            limits={},  # local providers have no rate limit
            is_local=True,
        )
        super().__init__(config)
        self._model = model
        assert self.dimensions == REQUIRED_DIMENSIONS, (
            f"Local embedding dimension mismatch: {self.dimensions} != {REQUIRED_DIMENSIONS}. "
            "Choose a 768-dim model (Path A) or migrate aep_memory.embedding."
        )
        log.info(
            "local_embedding.provider.initialized",
            model=model,
            dimensions=self.dimensions,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        raise NotImplementedError("LocalEmbeddingProvider only supports embeddings")

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        raise NotImplementedError("LocalEmbeddingProvider only supports embeddings")

    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        return [_embed_text(text, self.dimensions) for text in texts]

    def is_configured(self) -> bool:
        """Always configured — no API key required."""
        return True
