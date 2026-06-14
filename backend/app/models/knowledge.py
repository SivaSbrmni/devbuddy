"""Knowledge model for storing extracted conversation knowledge."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class KnowledgeEntry(BaseModel):
    """A single knowledge entry extracted from conversations."""
    
    id: UUID = Field(default_factory=uuid4)
    conversation_id: str
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)
    category: str = "general"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


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
