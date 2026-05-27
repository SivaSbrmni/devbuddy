"""
Compatibility Adapter Layer.

Per the AEP spec §3.2 the autonomous engineering layer must NEVER
modify existing service interfaces. Instead, it attaches itself
through a small set of strongly-typed extension hooks defined here.

Existing services call into the adapter at well-defined points:

    * before / after a Task is created
    * before / after a Task state transition
    * before / after an LLM call

Every hook is a no-op when the AEP master flag is off (or when nothing
is registered). The order in which hooks fire is the order they were
registered.

In Phase 0 nothing actually registers hooks; the layer ships as plumbing
so that subsequent phases can attach behavior without touching the
existing service modules.

Usage from an existing service::

    from app.aep.compat import get_compatibility_adapter

    adapter = get_compatibility_adapter()
    await adapter.dispatch_pre_task_create(payload)
    task = await task_service.create_task(...)
    await adapter.dispatch_post_task_create(task)

Registering a hook (typically from a Phase 1+ module)::

    @adapter.on_pre_llm_call
    async def my_hook(payload: LlmCallPayload) -> None:
        ...
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

from app.core.logger import get_logger

logger = get_logger("aep.compat")


# ─────────────────────────────────────────────────────────────────────────────
# Payload dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TaskCreatePayload:
    """Payload for ``pre_task_create`` / ``post_task_create`` hooks.

    Hooks may inspect but should not mutate the payload — any side
    effects belong on a downstream service call.
    """

    tenant_id: str
    created_by: str
    title: str
    description: Optional[str] = None
    repo_id: Optional[str] = None
    branch: Optional[str] = None
    policy_profile: str = "standard"
    metadata: dict[str, Any] = field(default_factory=dict)
    # Filled in for ``post_*`` hooks only.
    task_id: Optional[str] = None
    state: Optional[str] = None


@dataclass
class StateTransitionPayload:
    """Payload for the state-transition hooks."""

    tenant_id: str
    task_id: str
    from_state: str
    to_state: str
    actor_type: str
    actor_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class LlmCallPayload:
    """Payload for the LLM call hooks.

    ``response`` and ``usage`` are filled in for ``post_*`` hooks only.
    """

    tenant_id: Optional[str]
    provider: str
    model: str
    prompt_preview: str
    purpose: str = "generic"
    request: dict[str, Any] = field(default_factory=dict)
    response: Optional[str] = None
    usage: dict[str, int] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None


PayloadT = TypeVar(
    "PayloadT",
    TaskCreatePayload,
    StateTransitionPayload,
    LlmCallPayload,
)

#: A hook is an async (or sync) callable accepting one payload.
HookFn = Callable[[PayloadT], Awaitable[None] | None]


# ─────────────────────────────────────────────────────────────────────────────
# Hook channel
# ─────────────────────────────────────────────────────────────────────────────


class _Channel(Generic[PayloadT]):
    """Ordered set of hooks for a single extension point."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._hooks: list[HookFn[PayloadT]] = []

    def register(self, hook: HookFn[PayloadT]) -> HookFn[PayloadT]:
        self._hooks.append(hook)
        logger.debug("hook_registered", channel=self.name, hook=getattr(hook, "__qualname__", repr(hook)))
        return hook

    def unregister(self, hook: HookFn[PayloadT]) -> bool:
        try:
            self._hooks.remove(hook)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        self._hooks.clear()

    def __len__(self) -> int:
        return len(self._hooks)

    async def dispatch(self, payload: PayloadT) -> None:
        if not self._hooks:
            return
        for hook in list(self._hooks):
            try:
                result = hook(payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                # Hooks must never break the host call. Log and continue.
                logger.warning(
                    "hook_failed",
                    channel=self.name,
                    hook=getattr(hook, "__qualname__", repr(hook)),
                    error=str(exc),
                )


# ─────────────────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────────────────


class CompatibilityAdapter:
    """Hook registry and dispatcher for the AEP integration seams.

    A single instance lives for the lifetime of the application; obtain
    it via :func:`get_compatibility_adapter`.
    """

    def __init__(self) -> None:
        self._pre_task_create: _Channel[TaskCreatePayload] = _Channel("pre_task_create")
        self._post_task_create: _Channel[TaskCreatePayload] = _Channel("post_task_create")
        self._pre_state_transition: _Channel[StateTransitionPayload] = _Channel(
            "pre_state_transition"
        )
        self._post_state_transition: _Channel[StateTransitionPayload] = _Channel(
            "post_state_transition"
        )
        self._pre_llm_call: _Channel[LlmCallPayload] = _Channel("pre_llm_call")
        self._post_llm_call: _Channel[LlmCallPayload] = _Channel("post_llm_call")
        self._lock = asyncio.Lock()

    # ── Registration decorators ─────────────────────────────────────────

    def on_pre_task_create(
        self, fn: HookFn[TaskCreatePayload]
    ) -> HookFn[TaskCreatePayload]:
        return self._pre_task_create.register(fn)

    def on_post_task_create(
        self, fn: HookFn[TaskCreatePayload]
    ) -> HookFn[TaskCreatePayload]:
        return self._post_task_create.register(fn)

    def on_pre_state_transition(
        self, fn: HookFn[StateTransitionPayload]
    ) -> HookFn[StateTransitionPayload]:
        return self._pre_state_transition.register(fn)

    def on_post_state_transition(
        self, fn: HookFn[StateTransitionPayload]
    ) -> HookFn[StateTransitionPayload]:
        return self._post_state_transition.register(fn)

    def on_pre_llm_call(self, fn: HookFn[LlmCallPayload]) -> HookFn[LlmCallPayload]:
        return self._pre_llm_call.register(fn)

    def on_post_llm_call(self, fn: HookFn[LlmCallPayload]) -> HookFn[LlmCallPayload]:
        return self._post_llm_call.register(fn)

    # ── Programmatic unregister (mainly for tests) ──────────────────────

    def unregister(self, channel: str, fn: HookFn[Any]) -> bool:
        ch = self._channel(channel)
        return ch.unregister(fn)

    def clear(self, channel: Optional[str] = None) -> None:
        if channel is None:
            for ch in self._all_channels():
                ch.clear()
        else:
            self._channel(channel).clear()

    # ── Dispatchers ─────────────────────────────────────────────────────

    async def dispatch_pre_task_create(self, payload: TaskCreatePayload) -> None:
        await self._pre_task_create.dispatch(payload)

    async def dispatch_post_task_create(self, payload: TaskCreatePayload) -> None:
        await self._post_task_create.dispatch(payload)

    async def dispatch_pre_state_transition(
        self, payload: StateTransitionPayload
    ) -> None:
        await self._pre_state_transition.dispatch(payload)

    async def dispatch_post_state_transition(
        self, payload: StateTransitionPayload
    ) -> None:
        await self._post_state_transition.dispatch(payload)

    async def dispatch_pre_llm_call(self, payload: LlmCallPayload) -> None:
        await self._pre_llm_call.dispatch(payload)

    async def dispatch_post_llm_call(self, payload: LlmCallPayload) -> None:
        await self._post_llm_call.dispatch(payload)

    # ── Introspection ───────────────────────────────────────────────────

    def hook_counts(self) -> dict[str, int]:
        """Return ``{channel_name: hook_count}`` for diagnostics."""
        return {ch.name: len(ch) for ch in self._all_channels()}

    # ── Internals ───────────────────────────────────────────────────────

    def _all_channels(self) -> list[_Channel[Any]]:
        return [
            self._pre_task_create,
            self._post_task_create,
            self._pre_state_transition,
            self._post_state_transition,
            self._pre_llm_call,
            self._post_llm_call,
        ]

    def _channel(self, name: str) -> _Channel[Any]:
        mapping = {ch.name: ch for ch in self._all_channels()}
        if name not in mapping:
            raise ValueError(
                f"unknown hook channel {name!r}; "
                f"known channels: {sorted(mapping)}"
            )
        return mapping[name]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────

_adapter: Optional[CompatibilityAdapter] = None


def get_compatibility_adapter() -> CompatibilityAdapter:
    """Return the application-wide :class:`CompatibilityAdapter`."""
    global _adapter
    if _adapter is None:
        _adapter = CompatibilityAdapter()
    return _adapter


def reset_compatibility_adapter() -> None:
    """Reset the singleton. Test-only helper."""
    global _adapter
    _adapter = None


__all__ = [
    "TaskCreatePayload",
    "StateTransitionPayload",
    "LlmCallPayload",
    "HookFn",
    "CompatibilityAdapter",
    "get_compatibility_adapter",
    "reset_compatibility_adapter",
]
