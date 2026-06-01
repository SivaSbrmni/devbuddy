"""Tests for the AEP Context Engine — Phase 4."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.aep.memory.context_engine import ContextEngine, get_context_engine


class TestSummariseFile:
    """Summarisation logic tests."""

    @pytest.mark.asyncio
    async def test_short_file_returns_as_is(self) -> None:
        engine = ContextEngine()
        result = await engine._summarise_file("README.md", "short")
        assert "README.md" in result
        assert "short" in result

    @pytest.mark.asyncio
    async def test_long_file_calls_llm(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value={"text": "A utility module."})
        engine = ContextEngine(llm=mock_llm)

        content = "x" * 200
        result = await engine._summarise_file("utils.py", content)
        assert result == "A utility module."
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        engine = ContextEngine(llm=mock_llm)

        content = "x" * 200
        result = await engine._summarise_file("broken.py", content)
        assert "broken.py" in result


class TestRetrieveSimilar:
    """Retrieval logic tests (mocked DB and LLM)."""

    @pytest.mark.asyncio
    async def test_empty_embeddings_returns_empty(self) -> None:
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value={"embeddings": []})
        engine = ContextEngine(llm=mock_llm)

        mock_db = AsyncMock()
        result = await engine.retrieve_similar(
            query="test query",
            tenant_id=uuid.uuid4(),
            db=mock_db,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_token_budget_truncation(self) -> None:
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value={
            "embeddings": [[0.1] * 768],
            "model": "nomic-embed-text",
        })
        engine = ContextEngine(llm=mock_llm)

        row1 = MagicMock(
            id=uuid.uuid4(), memory_type="file_summary", key="a.py",
            content="content1", token_count=3000, similarity=0.95,
        )
        row2 = MagicMock(
            id=uuid.uuid4(), memory_type="file_summary", key="b.py",
            content="content2", token_count=3000, similarity=0.90,
        )
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row1, row2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        entries = await engine.retrieve_similar(
            query="test",
            tenant_id=uuid.uuid4(),
            token_budget=4000,
            db=mock_db,
        )
        assert len(entries) == 1
        assert entries[0]["key"] == "a.py"


class TestSingleton:
    """Singleton pattern test."""

    def test_get_context_engine_returns_same_instance(self) -> None:
        with patch("app.aep.memory.context_engine._singleton", None):
            e1 = get_context_engine()
            e2 = get_context_engine()
            assert e1 is e2
