"""
Shared types used by the agent plugin system.

These data structures are deliberately framework-agnostic — they are
the contract between the AEP orchestrator (Coordinator agent in
Phase 5) and the individual agent plugins.

Every type is a Pydantic v2 model so it serialises cleanly through
the FastAPI WebSocket layer and into the audit log.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentMessageKind(str, Enum):
    """Kinds of inter-agent messages exchanged through shared memory."""

    REQUEST = "request"
    RESPONSE = "response"
    OBSERVATION = "observation"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class AgentMessage(BaseModel):
    """Structured message exchanged between cooperating agents.

    Mirrors the spec §6.3 ``AgentMessage`` TypeScript shape so the
    frontend can render it without translation.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    execution_id: uuid.UUID
    sender: str
    recipient: Optional[str] = None
    kind: AgentMessageKind = AgentMessageKind.REQUEST
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentInput(BaseModel):
    """Input envelope handed to :meth:`AgentPlugin.execute`."""

    tenant_id: uuid.UUID
    execution_id: uuid.UUID
    step_index: int
    repository_id: Optional[uuid.UUID] = None
    branch: Optional[str] = None
    task_description: str = ""
    upstream: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """Result returned by :meth:`AgentPlugin.execute`."""

    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    messages: list[AgentMessage] = Field(default_factory=list)
    token_input: int = 0
    token_output: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    follow_up: list[str] = Field(default_factory=list)


class ExecutionPlanStep(BaseModel):
    """A single step in an :class:`ExecutionPlan`."""

    step_index: int
    agent_name: str
    description: str
    depends_on: list[int] = Field(default_factory=list)
    estimated_tokens: int = 0
    requires_github_actions: bool = False


class ExecutionPlan(BaseModel):
    """Planner Agent output (spec §6.1, Planner)."""

    execution_id: uuid.UUID
    version: int = 1
    summary: str
    steps: list[ExecutionPlanStep]
    estimated_tokens: int = 0
    requires_github_actions: bool = False
    notes: Optional[str] = None


__all__ = [
    "AgentMessage",
    "AgentMessageKind",
    "AgentInput",
    "AgentOutput",
    "ExecutionPlan",
    "ExecutionPlanStep",
]
