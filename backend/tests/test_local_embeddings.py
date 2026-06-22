"""Tests for Priority 4 — Local Embeddings."""

from __future__ import annotations

import asyncio
import math

import pytest

from app.llm.providers.local_embedding import LocalEmbeddingProvider, _embed_text, REQUIRED_DIMENSIONS
from app.llm.gateway import LLMGateway


class TestLocalEmbeddingProvider:
    """Local embeddings are 768-dim, deterministic, and bypass quota."""

    def test_dimension_asserted(self):
        provider = LocalEmbeddingProvider()
        assert provider.dimensions == REQUIRED_DIMENSIONS
        assert provider.config.is_local is True

    def test_embedding_deterministic(self):
        v1 = _embed_text("hello world", REQUIRED_DIMENSIONS)
        v2 = _embed_text("hello world", REQUIRED_DIMENSIONS)
        assert v1 == v2

    def test_embedding_dimensions_match_memory_column(self):
        v = _embed_text("hello", REQUIRED_DIMENSIONS)
        assert len(v) == REQUIRED_DIMENSIONS

    def test_different_inputs_produce_different_embeddings(self):
        v1 = _embed_text("hello", REQUIRED_DIMENSIONS)
        v2 = _embed_text("goodbye", REQUIRED_DIMENSIONS)
        assert v1 != v2

    def test_embeddings_normalized(self):
        v = _embed_text("normalize me", REQUIRED_DIMENSIONS)
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_provider_is_configured_without_key(self):
        provider = LocalEmbeddingProvider()
        assert provider.is_configured() is True

    @pytest.mark.asyncio
    async def test_embeddings_returns_correct_shape(self):
        provider = LocalEmbeddingProvider()
        result = await provider.embeddings(["a", "b", "c"], "local-onnx")
        assert len(result) == 3
        assert all(len(v) == REQUIRED_DIMENSIONS for v in result)

    def test_gateway_bypasses_quota_for_local_provider(self):
        gateway = LLMGateway()
        gateway.initialize = lambda: None
        gateway._initialized = True
        local = LocalEmbeddingProvider()
        gateway.providers = {local.name: local}
        gateway._default_cascade = [(local.name, "local-onnx")]

        # Quota ledger is empty but would_exceed should not be called for local
        # We just verify the provider is selected and the call succeeds
        result = asyncio.get_event_loop().run_until_complete(
            gateway.embeddings(["hello"], "local-onnx")
        )
        assert len(result) == 1
        assert len(result[0]) == REQUIRED_DIMENSIONS
