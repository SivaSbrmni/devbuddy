"""MCP (Model Context Protocol) API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.mcp_manager import mcp_manager
from app.models.mcp import MCPConfig, MCPTool, MCPToolCall, MCPToolResult

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers")
async def list_servers() -> list[MCPConfig]:
    """List all registered MCP servers."""
    return mcp_manager.list_servers()


@router.post("/servers")
async def register_server(config: MCPConfig) -> MCPConfig:
    """Register a new MCP server."""
    return mcp_manager.register_server(config)


@router.get("/servers/{server_id}")
async def get_server(server_id: str) -> Optional[MCPConfig]:
    """Get server configuration by ID."""
    server = mcp_manager.get_server(UUID(server_id))
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str) -> list[MCPTool]:
    """List available tools from a server."""
    return mcp_manager.list_tools(UUID(server_id))


@router.post("/tools/call")
async def call_tool(call: MCPToolCall) -> MCPToolResult:
    """Execute an MCP tool call."""
    return await mcp_manager.call_tool(call)


@router.get("/tools")
async def list_all_tools() -> list[dict]:
    """List all available tools from all enabled servers."""
    all_tools = []
    for server in mcp_manager.list_servers():
        if server.enabled:
            tools = mcp_manager.list_tools(server.id)
            for tool in tools:
                all_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "server_id": str(tool.server_id),
                    "server_name": server.name,
                    "server_type": server.server_type
                })
    return all_tools
