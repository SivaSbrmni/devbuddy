"""Tests for the execution state machine — Phase 3."""
import pytest

from app.aep.execution.state_machine import (
    ExecutionStateMachine,
    InvalidTransitionError,
    VALID_TRANSITIONS,
)
from app.aep.models import AepExecutionState


class TestExecutionStateMachine:
    """FSM transition logic."""

    def test_initial_state(self) -> None:
        fsm = ExecutionStateMachine()
        assert fsm.state == "PENDING"

    def test_custom_initial_state(self) -> None:
        fsm = ExecutionStateMachine("EXECUTING")
        assert fsm.state == "EXECUTING"

    def test_is_terminal_false(self) -> None:
        fsm = ExecutionStateMachine()
        assert fsm.is_terminal is False

    def test_is_terminal_completed(self) -> None:
        fsm = ExecutionStateMachine("COMPLETED")
        assert fsm.is_terminal is True

    def test_is_terminal_failed(self) -> None:
        fsm = ExecutionStateMachine("FAILED")
        assert fsm.is_terminal is True

    def test_is_terminal_cancelled(self) -> None:
        fsm = ExecutionStateMachine("CANCELLED")
        assert fsm.is_terminal is True

    def test_can_transition_valid(self) -> None:
        fsm = ExecutionStateMachine()
        assert fsm.can_transition("PLANNING") is True

    def test_can_transition_invalid(self) -> None:
        fsm = ExecutionStateMachine()
        assert fsm.can_transition("COMPLETED") is False

    @pytest.mark.asyncio
    async def test_transition_valid(self) -> None:
        fsm = ExecutionStateMachine()
        result = await fsm.transition(
            "PLANNING",
            tenant_id="t1",
            task_id="task1",
        )
        assert result == "PLANNING"
        assert fsm.state == "PLANNING"

    @pytest.mark.asyncio
    async def test_transition_invalid_raises(self) -> None:
        fsm = ExecutionStateMachine()
        with pytest.raises(InvalidTransitionError):
            await fsm.transition(
                "COMPLETED",
                tenant_id="t1",
                task_id="task1",
            )

    @pytest.mark.asyncio
    async def test_full_happy_path(self) -> None:
        fsm = ExecutionStateMachine()
        kwargs = {"tenant_id": "t1", "task_id": "task1"}

        await fsm.transition("PLANNING", **kwargs)
        assert fsm.state == "PLANNING"

        await fsm.transition("AWAITING_APPROVAL", **kwargs)
        assert fsm.state == "AWAITING_APPROVAL"

        await fsm.transition("EXECUTING", **kwargs)
        assert fsm.state == "EXECUTING"

        await fsm.transition("VALIDATING", **kwargs)
        assert fsm.state == "VALIDATING"

        await fsm.transition("COMPLETED", **kwargs)
        assert fsm.state == "COMPLETED"
        assert fsm.is_terminal is True

    @pytest.mark.asyncio
    async def test_cancel_from_pending(self) -> None:
        fsm = ExecutionStateMachine()
        await fsm.transition(
            "CANCELLED", tenant_id="t1", task_id="task1",
        )
        assert fsm.state == "CANCELLED"
        assert fsm.is_terminal is True

    @pytest.mark.asyncio
    async def test_fail_from_executing(self) -> None:
        fsm = ExecutionStateMachine("EXECUTING")
        await fsm.transition(
            "FAILED", tenant_id="t1", task_id="task1",
        )
        assert fsm.state == "FAILED"
        assert fsm.is_terminal is True

    def test_all_states_have_transitions(self) -> None:
        """Every AepExecutionState value must be in the transition table."""
        for state in AepExecutionState:
            assert state.value in VALID_TRANSITIONS, f"{state.value} missing from VALID_TRANSITIONS"

    def test_terminal_states_have_no_transitions(self) -> None:
        for terminal in ("COMPLETED", "FAILED", "CANCELLED"):
            assert VALID_TRANSITIONS[terminal] == set()
