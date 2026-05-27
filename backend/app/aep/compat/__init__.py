"""Compatibility Adapter Layer — public re-exports."""

from app.aep.compat.adapter import (
    CompatibilityAdapter,
    HookFn,
    LlmCallPayload,
    StateTransitionPayload,
    TaskCreatePayload,
    get_compatibility_adapter,
    reset_compatibility_adapter,
)

__all__ = [
    "CompatibilityAdapter",
    "HookFn",
    "LlmCallPayload",
    "StateTransitionPayload",
    "TaskCreatePayload",
    "get_compatibility_adapter",
    "reset_compatibility_adapter",
]
