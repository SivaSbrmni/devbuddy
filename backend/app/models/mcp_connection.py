import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class McpConnection(Base):
    __tablename__ = "mcp_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # type: loki | datadog | cloudwatch | custom_http | custom_mcp
    conn_type: Mapped[str] = mapped_column(String(50), nullable=False, default="custom_http")
    url: Mapped[str] = mapped_column(Text, nullable=True)        # base URL for HTTP-based MCPs
    api_key: Mapped[str] = mapped_column(Text, nullable=True)    # stored encrypted (placeholder)
    config: Mapped[dict] = mapped_column(JSON, default=dict)     # extra params (headers, logql, etc.)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tested_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool] = mapped_column(Boolean, nullable=True)
    last_test_msg: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
