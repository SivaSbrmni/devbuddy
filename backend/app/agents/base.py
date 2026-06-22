"""Base agent — shared lifecycle for all autonomous agents."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_router import LLMRequest, LLMResponse, ModelRouter, TaskCategory
from app.models.task import AgentStep

log = structlog.get_logger()


class BaseAgent(ABC):
    """Every agent inherits from this.

    Provides:
    - LLM access through the model router (never call LLM directly)
    - Step tracking (persisted to agent_steps table)
    - Structured logging
    """

    name: str = "base"

    def __init__(self, router: ModelRouter, db: AsyncSession) -> None:
        self.router = router
        self.db = db

    # ── public entry point ──────────────────────────────────────────
    async def run(self, task_id: uuid.UUID, context: dict[str, Any]) -> dict[str, Any]:
        log.info(f"agent.{self.name}.start", task_id=str(task_id))
        start = time.monotonic()
        try:
            result = await self.execute(context)
            duration = int((time.monotonic() - start) * 1000)
            await self._record_step(task_id, "execute", context, result, "completed", duration)
            log.info(f"agent.{self.name}.done", task_id=str(task_id), duration_ms=duration)
            return result
        except Exception as exc:
            duration = int((time.monotonic() - start) * 1000)
            await self._record_step(
                task_id, "execute", context, {"error": str(exc)}, "failed", duration
            )
            log.error(f"agent.{self.name}.failed", task_id=str(task_id), error=str(exc))
            raise

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Subclass implements the actual agent logic here."""

    # ── helpers ──────────────────────────────────────────────────────
    async def llm(
        self,
        messages: list[dict[str, str]],
        category: TaskCategory,
        *,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        memoize_context: dict[str, Any] | None = None,
    ) -> LLMResponse:
        return await self.router.complete(
            LLMRequest(
                messages=messages,
                task_category=category,
                system_prompt=system,
                max_tokens=max_tokens,
                temperature=temperature,
                memoize_context=memoize_context,
            )
        )

    async def _record_step(
        self,
        task_id: uuid.UUID,
        action: str,
        input_data: dict,
        output_data: dict,
        status: str,
        duration_ms: int,
        tokens_used: int = 0,
        model_used: str | None = None,
    ) -> None:
        step = AgentStep(
            task_id=task_id,
            agent_name=self.name,
            action=action,
            input_data=input_data,
            output_data=output_data,
            status=status,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            model_used=model_used,
        )
        self.db.add(step)
        await self.db.flush()
