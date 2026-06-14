"""MCP (Model Context Protocol) configuration models."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MCPConfig(BaseModel):
    """MCP server configuration."""
    
    id: UUID = Field(default_factory=uuid4)
    name: str
    server_type: str  # e.g., 'github', 'huggingface', 'filesystem', 'database'
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    config: dict = Field(default_factory=dict)
    enabled: bool = True
    
    class Config:
        from_attributes = True


class MCPTool(BaseModel):
    """Available tool from an MCP server."""
    
    name: str
    description: str
    input_schema: dict
    server_id: UUID


class MCPToolCall(BaseModel):
    """Request to call an MCP tool."""
    
    server_id: UUID
    tool_name: str
    arguments: dict


class MCPToolResult(BaseModel):
    """Result from an MCP tool call."""
    
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
