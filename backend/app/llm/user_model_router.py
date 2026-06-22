"""Per-user ModelRouter adapter for the autonomous agent pipeline.

The legacy ModelRouter is a singleton driven by environment variables. This
adapter lets the agent orchestrator use the same user-configured LLM providers
(UserLLMProvider) that the chat endpoint uses, while preserving the
ModelRouter.complete() interface the agents expect.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.model_router import LLMRequest, LLMResponse, ModelRouter, TaskCategory
from app.llm.gateway import LLMGateway, initialize_gateway_for_user
from app.llm.providers.user_provider import UserProviderAdapter


# Best-effort mapping from the legacy TaskCategory to gateway task types.
_TASK_CATEGORY_TO_TYPE: dict[TaskCategory, str] = {
    TaskCategory.REQUIREMENT_ANALYSIS: "planner",
    TaskCategory.PLANNING_DRAFT: "planner",
    TaskCategory.TASK_DECOMPOSITION: "planner",
    TaskCategory.WORKFLOW_ORCHESTRATION: "planner",
    TaskCategory.CONTEXT_COMPRESSION: "summarization",
    TaskCategory.SUMMARIZATION: "summarization",
    TaskCategory.LOG_ANALYSIS: "log_analysis",
    TaskCategory.STATUS_REPORTING: "status_reporting",
    TaskCategory.REQUIREMENTS_REVIEW: "reviewer",
    TaskCategory.ARCHITECTURE_REVIEW: "reviewer",
    TaskCategory.SYSTEM_DESIGN: "architect",
    TaskCategory.DATABASE_DESIGN: "architect",
    TaskCategory.API_DESIGN: "architect",
    TaskCategory.CODING: "coder",
    TaskCategory.CODE_REVIEW: "reviewer",
    TaskCategory.REFACTORING: "coder",
    TaskCategory.SECURITY_REVIEW: "security",
    TaskCategory.TEST_GENERATION: "test",
    TaskCategory.ROOT_CAUSE_ANALYSIS: "debugger",
    TaskCategory.DEBUGGING: "debugger",
    TaskCategory.DEPLOYMENT_VALIDATION: "devops",
    TaskCategory.FINAL_APPROVAL: "reviewer",
}


class UserModelRouter(ModelRouter):
    """ModelRouter that routes every call through the user's LLM providers.

    Usage:
        router = UserModelRouter(user_id=user.id, db=db, default_model="qwen3-coder:480b")
        await router.initialize(user)
        response = await router.complete(LLMRequest(...))
    """

    def __init__(
        self,
        user_id: uuid.UUID,
        db: Any,
        default_model: str | None = None,
    ) -> None:
        # Skip the env-based ModelRouter initialization; we use LLMGateway.
        super().__init__()
        self.user_id = user_id
        self.db = db
        self.default_model = default_model
        self._gateway: LLMGateway | None = None
        self._user: Any | None = None

    @property
    def has_providers(self) -> bool:
        """Return True if the gateway has at least one configured provider."""
        return self._gateway is not None and bool(self._gateway.providers)

    async def initialize(self, user: Any | None = None) -> None:
        """Load the user's provider cascade."""
        self._gateway = LLMGateway(user_id=self.user_id, db=self.db)
        if user is None:
            from sqlalchemy import select
            from app.models.user import User

            result = await self.db.execute(select(User).where(User.id == self.user_id))
            user = result.scalar_one_or_none()
        self._user = user
        if user:
            await initialize_gateway_for_user(self._gateway, user)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Fulfill a ModelRouter-style request via the user's LLM providers."""
        if self._gateway is None or self._user is None:
            raise RuntimeError("UserModelRouter not initialized. Call initialize() first.")

        task_type = _TASK_CATEGORY_TO_TYPE.get(request.task_category, "coder")
        response = await self._gateway.chat(
            messages=request.messages,
            task_type=task_type,
            model=request.model or self.default_model,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return LLMResponse(
            content=response.text,
            provider=response.provider,
            model=response.model,
            input_tokens=response.usage.get("input_tokens", 0),
            output_tokens=response.usage.get("output_tokens", 0),
            latency_ms=response.latency_ms,
            cost_usd=self._estimate_cost(response),
        )

    def _estimate_cost(self, response) -> float:
        """Estimate cost from the provider's configured rates, if available."""
        if not self._gateway or not response.provider:
            return 0.0
        provider = self._gateway.providers.get(response.provider)
        if not isinstance(provider, UserProviderAdapter):
            return 0.0
        record = provider.record
        input_tokens = response.usage.get("input_tokens", 0)
        output_tokens = response.usage.get("output_tokens", 0)
        return (
            input_tokens * (record.cost_per_1k_input or 0.0) / 1000
            + output_tokens * (record.cost_per_1k_output or 0.0) / 1000
        )
