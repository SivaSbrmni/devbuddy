import uuid
from sqlalchemy import String, Text, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class AgentMemory(Base):
    """
    Stores per-user long-term memories as embedded text.
    The `vector` column holds a JSON-serialised list[float] (embedding).
    Similarity search is done in Python (cosine) so no pgvector extension is required.
    """
    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="conversation")
    vector: Mapped[str] = mapped_column(Text, nullable=False)
    extra_meta: Mapped[str] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        Index("ix_agent_memories_user_created", "user_id", "created_at"),
    )
