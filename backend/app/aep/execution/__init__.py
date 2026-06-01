"""AEP Execution Engine — Phase 3.

FSM-driven execution of autonomous engineering tasks through the
planning → approval → execution → validation pipeline.
"""

from app.aep.execution.state_machine import ExecutionStateMachine
from app.aep.execution.service import ExecutionService, get_execution_service

__all__ = ["ExecutionStateMachine", "ExecutionService", "get_execution_service"]
