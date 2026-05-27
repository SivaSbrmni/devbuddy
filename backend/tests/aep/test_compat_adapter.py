"""Tests for the Compatibility Adapter Layer."""
from __future__ import annotations

import asyncio

import pytest

from app.aep.compat import (
    CompatibilityAdapter,
    LlmCallPayload,
    StateTransitionPayload,
    TaskCreatePayload,
    get_compatibility_adapter,
    reset_compatibility_adapter,
)


@pytest.fixture(autouse=True)
def _reset_adapter():
    reset_compatibility_adapter()
    yield
    reset_compatibility_adapter()


class TestDispatchWhenEmpty:
    """With zero hooks registered, every dispatch must be a no-op."""

    async def test_pre_task_create_noop(self):
        adapter = CompatibilityAdapter()
        await adapter.dispatch_pre_task_create(
            TaskCreatePayload(tenant_id="t", created_by="u", title="x")
        )

    async def test_pre_llm_call_noop(self):
        adapter = CompatibilityAdapter()
        await adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=None,
                provider="ollama",
                model="llama3.2",
                prompt_preview="hello",
            )
        )

    async def test_state_transition_noop(self):
        adapter = CompatibilityAdapter()
        await adapter.dispatch_pre_state_transition(
            StateTransitionPayload(
                tenant_id="t",
                task_id="x",
                from_state="PENDING",
                to_state="EXECUTING",
                actor_type="system",
            )
        )

    def test_hook_counts_are_zero(self):
        adapter = CompatibilityAdapter()
        counts = adapter.hook_counts()
        assert counts == {
            "pre_task_create": 0,
            "post_task_create": 0,
            "pre_state_transition": 0,
            "post_state_transition": 0,
            "pre_llm_call": 0,
            "post_llm_call": 0,
        }


class TestRegistration:
    async def test_hooks_fire_in_registration_order(self):
        adapter = CompatibilityAdapter()
        log: list[str] = []

        @adapter.on_pre_task_create
        async def first(_p: TaskCreatePayload) -> None:
            log.append("first")

        @adapter.on_pre_task_create
        def second(_p: TaskCreatePayload) -> None:
            log.append("second")

        await adapter.dispatch_pre_task_create(
            TaskCreatePayload(tenant_id="t", created_by="u", title="x")
        )
        assert log == ["first", "second"]

    async def test_sync_and_async_hooks_both_supported(self):
        adapter = CompatibilityAdapter()
        observed: list[str] = []

        @adapter.on_pre_llm_call
        def sync_hook(p: LlmCallPayload) -> None:
            observed.append(f"sync:{p.model}")

        @adapter.on_pre_llm_call
        async def async_hook(p: LlmCallPayload) -> None:
            await asyncio.sleep(0)
            observed.append(f"async:{p.model}")

        await adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=None,
                provider="ollama",
                model="m",
                prompt_preview="...",
            )
        )
        assert observed == ["sync:m", "async:m"]

    async def test_hook_failures_do_not_break_dispatch(self):
        adapter = CompatibilityAdapter()
        called: list[str] = []

        @adapter.on_pre_task_create
        def boom(_p: TaskCreatePayload) -> None:
            raise RuntimeError("hook exploded")

        @adapter.on_pre_task_create
        def survivor(_p: TaskCreatePayload) -> None:
            called.append("survivor")

        # Dispatch must not raise even though the first hook does.
        await adapter.dispatch_pre_task_create(
            TaskCreatePayload(tenant_id="t", created_by="u", title="x")
        )
        assert called == ["survivor"]

    def test_unregister(self):
        adapter = CompatibilityAdapter()

        def hook(_p: TaskCreatePayload) -> None:
            pass

        adapter.on_pre_task_create(hook)
        assert adapter.hook_counts()["pre_task_create"] == 1
        assert adapter.unregister("pre_task_create", hook) is True
        assert adapter.hook_counts()["pre_task_create"] == 0

    def test_unregister_missing_hook_returns_false(self):
        adapter = CompatibilityAdapter()

        def hook(_p: TaskCreatePayload) -> None:
            pass

        assert adapter.unregister("pre_task_create", hook) is False

    def test_clear_all_channels(self):
        adapter = CompatibilityAdapter()
        adapter.on_pre_task_create(lambda _p: None)
        adapter.on_post_task_create(lambda _p: None)
        adapter.clear()
        assert all(v == 0 for v in adapter.hook_counts().values())

    def test_unknown_channel_raises(self):
        adapter = CompatibilityAdapter()
        with pytest.raises(ValueError):
            adapter.unregister("not_a_channel", lambda _p: None)


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_compatibility_adapter()
        b = get_compatibility_adapter()
        assert a is b
