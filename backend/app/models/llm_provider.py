"""UserLLMProvider and routing rules - universal LLM endpoint architecture."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserLLMProvider(Base):
    """User-defined LLM endpoints - no code changes needed for new providers."""

    __tablename__ = "user_llm_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Display name (user-friendly)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Production GPT", "Local Ollama"

    # Provider type
    provider_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="openai-compatible"
    )  # openai-compatible, anthropic, ollama, google, azure, custom

    # Connection (encrypted at application level with Fernet)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet encrypted
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)  # Custom headers

    # Model configuration
    default_model: Mapped[str] = mapped_column(String(100), nullable=False)
    available_models: Mapped[list] = mapped_column(JSONB, default=list)  # ["gpt-4", "gpt-3.5-turbo"]

    # Capabilities
    supports_streaming: Mapped[bool] = mapped_column(default=True)
    supports_tools: Mapped[bool] = mapped_column(default=True)
    supports_vision: Mapped[bool] = mapped_column(default=False)
    context_size: Mapped[int] = mapped_column(default=8192)
    max_tokens: Mapped[int] = mapped_column(default=4096)

    # Cost tracking
    cost_per_1k_input: Mapped[float] = mapped_column(default=0.0)
    cost_per_1k_output: Mapped[float] = mapped_column(default=0.0)

    # Routing priority (lower = higher priority for default selection)
    priority: Mapped[int] = mapped_column(default=100)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)  # Use this unless overridden

    # Health checking
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_status: Mapped[str] = mapped_column(String(20), default="unknown")  # healthy, degraded, error, unknown
    health_message: Mapped[str] = mapped_column(String(255), default="")
    latency_ms: Mapped[int | None] = mapped_column()  # Last measured latency

    # Usage tracking
    request_count: Mapped[int] = mapped_column(default=0)
    token_count: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships - use lazy='select' to prevent mapper conflicts
    user: Mapped[User] = relationship("User", back_populates="llm_providers", lazy="select")
    routing_rules: Mapped[list["ProviderRoutingRule"]] = relationship(
        "ProviderRoutingRule",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="ProviderRoutingRule.provider_id",
    )

    __table_args__ = (
        Index("ix_llm_providers_user_id", "user_id"),
        Index("ix_llm_providers_active", "user_id", "is_active"),
        Index("ix_llm_providers_default", "user_id", "is_default"),
    )


class ProviderRoutingRule(Base):
    """LangGraph selects model automatically based on task type."""

    __tablename__ = "provider_routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_llm_providers.id"), nullable=False
    )

    # Task classification
    task_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )  # coding, planning, review, cheap_task, analysis, debugging, testing, documentation

    # Routing criteria
    priority: Mapped[int] = mapped_column(default=100)  # Lower = preferred
    max_cost_per_request: Mapped[float | None] = mapped_column()  # USD
    min_quality_score: Mapped[float | None] = mapped_column()  # 0-1
    speed_priority: Mapped[bool] = mapped_column(default=False)  # Prefer lower latency

    # Fallback chain
    fallback_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_llm_providers.id")
    )

    # Custom model override for this task type
    model_override: Mapped[str | None] = mapped_column(String(100))
    temperature_override: Mapped[float | None] = mapped_column()

    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships - use lazy='select' to prevent mapper conflicts
    provider: Mapped[UserLLMProvider] = relationship(
        "UserLLMProvider",
        back_populates="routing_rules",
        foreign_keys=[provider_id],
        lazy="select"
    )

    __table_args__ = (
        Index("ix_routing_rules_user_id", "user_id"),
        Index("ix_routing_rules_task", "user_id", "task_type"),
    )
