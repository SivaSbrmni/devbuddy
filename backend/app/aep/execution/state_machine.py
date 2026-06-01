"""Execution state machine — Phase 3.

Implements the FSM transitions from spec §6.2:

    PENDING → PLANNING → AWAITING_APPROVAL → EXECUTING → VALIDATING
                                                          → REVIEWING
                                                          → COMPLETED
                                                          → FAILED
                                                          → CANCELLED

Each transition fires ``pre/post_state_transition`` adapter hooks and
writes to ``aep_execution_steps``.
"""
from __future__ import annotations

from app.aep.compat import StateTransitionPayload, get_compatibility_adapter
from app.aep.models import AepExecutionState
from app.aep.observability import aep_logger

_logger = aep_logger("aep.execution.fsm")

VALID_TRANSITIONS: dict[str, set[str]] = {
    AepExecutionState.PENDING.value: {
        AepExecutionState.PLANNING.value,
        AepExecutionState.CANCELLED.value,
    },
    AepExecutionState.PLANNING.value: {
        AepExecutionState.AWAITING_APPROVAL.value,
        AepExecutionState.FAILED.value,
        AepExecutionState.CANCELLED.value,
    },
    AepExecutionState.AWAITING_APPROVAL.value: {
        AepExecutionState.EXECUTING.value,
        AepExecutionState.CANCELLED.value,
    },
    AepExecutionState.EXECUTING.value: {
        AepExecutionState.VALIDATING.value,
        AepExecutionState.FAILED.value,
        AepExecutionState.CANCELLED.value,
    },
    AepExecutionState.VALIDATING.value: {
        AepExecutionState.REVIEWING.value,
        AepExecutionState.COMPLETED.value,
        AepExecutionState.FAILED.value,
    },
    AepExecutionState.REVIEWING.value: {
        AepExecutionState.COMPLETED.value,
        AepExecutionState.FAILED.value,
    },
    AepExecutionState.COMPLETED.value: set(),
    AepExecutionState.FAILED.value: set(),
    AepExecutionState.CANCELLED.value: set(),
}


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, from_state: str, to_state: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition: {from_state} → {to_state}")


class ExecutionStateMachine:
    """Manages state transitions for an AEP execution."""

    def __init__(self, initial_state: str = AepExecutionState.PENDING.value) -> None:
        self._state = initial_state
        self._adapter = get_compatibility_adapter()

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in {
            AepExecutionState.COMPLETED.value,
            AepExecutionState.FAILED.value,
            AepExecutionState.CANCELLED.value,
        }

    def can_transition(self, to_state: str) -> bool:
        return to_state in VALID_TRANSITIONS.get(self._state, set())

    async def transition(
        self,
        to_state: str,
        *,
        tenant_id: str,
        task_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Execute a state transition with adapter hooks."""
        if not self.can_transition(to_state):
            raise InvalidTransitionError(self._state, to_state)

        from_state = self._state
        payload = StateTransitionPayload(
            tenant_id=tenant_id,
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        )

        await self._adapter.dispatch_pre_state_transition(payload)
        self._state = to_state
        await self._adapter.dispatch_post_state_transition(payload)

        _logger.info(
            "state_transition",
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            actor_type=actor_type,
        )
        return self._state
