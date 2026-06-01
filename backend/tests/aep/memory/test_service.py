"""Tests for the AEP Memory Service — Phase 4."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.aep.memory.service import MemoryService, RedisWorkingContext, get_memory_service


class TestRedisWorkingContext:
    """Redis working context tests (graceful degradation)."""

    @pytest.mark.asyncio
    async def test_store_returns_false_when_redis_unavailable(self) -> None:
        ctx = RedisWorkingContext()
        ctx._redis = None
        with patch.object(ctx, "_get_redis", new=AsyncMock(return_value=None)):
            result = await ctx.store(uuid.uuid4(), uuid.uuid4(), {"key": "val"})
        assert result is False

    @pytest.mark.asyncio
    async def test_recall_returns_empty_when_redis_unavailable(self) -> None:
        ctx = RedisWorkingContext()
        ctx._redis = None
        with patch.object(ctx, "_get_redis", new=AsyncMock(return_value=None)):
            data = await ctx.recall(uuid.uuid4(), uuid.uuid4())
        assert data == {}

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_redis_unavailable(self) -> None:
        ctx = RedisWorkingContext()
        ctx._redis = None
        with patch.object(ctx, "_get_redis", new=AsyncMock(return_value=None)):
            result = await ctx.delete(uuid.uuid4(), uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_store_and_recall_with_mock_redis(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"key": "val"}')

        ctx = RedisWorkingContext()
        ctx._redis = mock_redis

        tid = uuid.uuid4()
        eid = uuid.uuid4()

        result = await ctx.store(tid, eid, {"key": "val"})
        assert result is True
        mock_redis.set.assert_called_once()

        data = await ctx.recall(tid, eid)
        assert data == {"key": "val"}

    @pytest.mark.asyncio
    async def test_recall_returns_empty_for_missing_key(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        ctx = RedisWorkingContext()
        ctx._redis = mock_redis

        data = await ctx.recall(uuid.uuid4(), uuid.uuid4())
        assert data == {}

    def test_key_format(self) -> None:
        ctx = RedisWorkingContext()
        tid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        eid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        key = ctx._key(tid, eid)
        assert key == "aep:12345678-1234-5678-1234-567812345678:working:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class TestMemoryService:
    """MemoryService orchestration tests."""

    @pytest.mark.asyncio
    async def test_store_working_context_delegates(self) -> None:
        mock_working = AsyncMock(spec=RedisWorkingContext)
        mock_working.store = AsyncMock(return_value=True)
        svc = MemoryService(working_ctx=mock_working)

        tid = uuid.uuid4()
        eid = uuid.uuid4()
        result = await svc.store_working_context(tid, eid, {"data": 1})
        assert result is True
        mock_working.store.assert_called_once_with(tid, eid, {"data": 1})

    @pytest.mark.asyncio
    async def test_recall_working_context_delegates(self) -> None:
        mock_working = AsyncMock(spec=RedisWorkingContext)
        mock_working.recall = AsyncMock(return_value={"data": 1})
        svc = MemoryService(working_ctx=mock_working)

        tid = uuid.uuid4()
        eid = uuid.uuid4()
        data = await svc.recall_working_context(tid, eid)
        assert data == {"data": 1}

    @pytest.mark.asyncio
    async def test_retrieve_similar_delegates(self) -> None:
        mock_ctx = AsyncMock()
        mock_ctx.retrieve_similar = AsyncMock(return_value=[{"content": "match"}])
        svc = MemoryService(context_engine=mock_ctx)

        mock_db = AsyncMock()
        results = await svc.retrieve_similar(
            query="test", tenant_id=uuid.uuid4(), db=mock_db,
        )
        assert len(results) == 1
        mock_ctx.retrieve_similar.assert_called_once()


class TestSingleton:

    def test_get_memory_service_returns_same_instance(self) -> None:
        with patch("app.aep.memory.service._singleton", None):
            s1 = get_memory_service()
            s2 = get_memory_service()
            assert s1 is s2
