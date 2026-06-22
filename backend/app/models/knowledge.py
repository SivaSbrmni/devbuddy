"""Knowledge model for storing extracted conversation knowledge."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class KnowledgeEntry(BaseModel):
    """A single knowledge entry extracted from conversations."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    conversation_id: str
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)
    category: str = "general"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class KnowledgeCreate(BaseModel):
    """Request to create a knowledge entry."""

    conversation_id: str
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)
    category: str = "general"


class KnowledgeSearch(BaseModel):
    """Request to search knowledge."""

    query: str
    category: Optional[str] = None
    limit: int = 10
