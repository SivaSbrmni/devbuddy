"""MCP (Model Context Protocol) manager for external service integration."""

from typing import Optional
from uuid import UUID

import httpx

from app.models.mcp import MCPConfig, MCPTool, MCPToolCall, MCPToolResult


class MCPManager:
    """Manages MCP server connections and tool execution."""

    def __init__(self):
        self.servers: dict[UUID, MCPConfig] = {}
        self._init_default_servers()

    def _init_default_servers(self):
        """Initialize default MCP server configurations."""
        # GitHub MCP
        self.servers[UUID("00000000-0000-0000-0000-000000000001")] = MCPConfig(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            name="GitHub",
            server_type="github",
            endpoint="https://api.github.com",
            config={"repo": "SivaSbrmni/devbuddy"},
            enabled=True
        )

        # HuggingFace MCP
        self.servers[UUID("00000000-0000-0000-0000-000000000002")] = MCPConfig(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            name="HuggingFace",
            server_type="huggingface",
            endpoint="https://huggingface.co/api",
            config={},
            enabled=True
        )

    def register_server(self, config: MCPConfig) -> MCPConfig:
        """Register a new MCP server."""
        self.servers[config.id] = config
        return config

    def get_server(self, server_id: UUID) -> Optional[MCPConfig]:
        """Get server configuration by ID."""
        return self.servers.get(server_id)

    def list_servers(self) -> list[MCPConfig]:
        """List all registered servers."""
        return list(self.servers.values())

    def list_tools(self, server_id: UUID) -> list[MCPTool]:
        """List available tools from a server."""
        server = self.get_server(server_id)
        if not server or not server.enabled:
            return []

        if server.server_type == "github":
            return self._github_tools(server_id)
        elif server.server_type == "huggingface":
            return self._huggingface_tools(server_id)
        else:
            return []

    def _github_tools(self, server_id: UUID) -> list[MCPTool]:
        """GitHub-specific tools."""
        return [
            MCPTool(
                name="search_repositories",
                description="Search GitHub repositories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 10}
                    }
                },
                server_id=server_id
            ),
            MCPTool(
                name="get_file",
                description="Get file content from repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                        "path": {"type": "string", "description": "File path"},
                        "branch": {"type": "string", "default": "main"}
                    }
                },
                server_id=server_id
            ),
            MCPTool(
                name="create_issue",
                description="Create a GitHub issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                        "title": {"type": "string", "description": "Issue title"},
                        "body": {"type": "string", "description": "Issue body"}
                    }
                },
                server_id=server_id
            )
        ]

    def _huggingface_tools(self, server_id: UUID) -> list[MCPTool]:
        """HuggingFace-specific tools."""
        return [
            MCPTool(
                name="search_models",
                description="Search HuggingFace models",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 10}
                    }
                },
                server_id=server_id
            ),
            MCPTool(
                name="get_model_info",
                description="Get model information",
                input_schema={
                    "type": "object",
                    "properties": {
                        "model_id": {"type": "string", "description": "Model ID (e.g., meta-llama/Llama-2-7b)"}
                    }
                },
                server_id=server_id
            )
        ]

    async def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        """Execute an MCP tool call."""
        server = self.get_server(call.server_id)
        if not server or not server.enabled:
            return MCPToolResult(success=False, error="Server not found or disabled")

        try:
            if server.server_type == "github":
                return await self._call_github_tool(server, call)
            elif server.server_type == "huggingface":
                return await self._call_huggingface_tool(server, call)
            else:
                return MCPToolResult(success=False, error=f"Unknown server type: {server.server_type}")
        except Exception as e:
            return MCPToolResult(success=False, error=str(e))

    async def _call_github_tool(self, server: MCPConfig, call: MCPToolCall) -> MCPToolResult:
        """Call GitHub API."""
        async with httpx.AsyncClient() as client:
            headers = {}
            if server.api_key:
                headers["Authorization"] = f"token {server.api_key}"

            if call.tool_name == "search_repositories":
                params = {
                    "q": call.arguments.get("query", ""),
                    "per_page": call.arguments.get("limit", 10)
                }
                resp = await client.get(f"{server.endpoint}/search/repositories", params=params, headers=headers)
                return MCPToolResult(success=True, result=resp.json())

            elif call.tool_name == "get_file":
                repo = call.arguments.get("repo", server.config.get("repo"))
                path = call.arguments.get("path")
                branch = call.arguments.get("branch", "main")
                resp = await client.get(
                    f"{server.endpoint}/repos/{repo}/contents/{path}",
                    params={"ref": branch},
                    headers=headers
                )
                data = resp.json()
                if "content" in data:
                    import base64
                    data["content"] = base64.b64decode(data["content"]).decode()
                return MCPToolResult(success=True, result=data)

            elif call.tool_name == "create_issue":
                repo = call.arguments.get("repo", server.config.get("repo"))
                resp = await client.post(
                    f"{server.endpoint}/repos/{repo}/issues",
                    json={
                        "title": call.arguments.get("title"),
                        "body": call.arguments.get("body")
                    },
                    headers=headers
                )
                return MCPToolResult(success=True, result=resp.json())

        return MCPToolResult(success=False, error="Unknown GitHub tool")

    async def _call_huggingface_tool(self, server: MCPConfig, call: MCPToolCall) -> MCPToolResult:
        """Call HuggingFace API."""
        async with httpx.AsyncClient() as client:
            headers = {}
            if server.api_key:
                headers["Authorization"] = f"Bearer {server.api_key}"

            if call.tool_name == "search_models":
                params = {
                    "q": call.arguments.get("query", ""),
                    "limit": call.arguments.get("limit", 10)
                }
                resp = await client.get(f"{server.endpoint}/models", params=params, headers=headers)
                return MCPToolResult(success=True, result=resp.json())

            elif call.tool_name == "get_model_info":
                model_id = call.arguments.get("model_id")
                resp = await client.get(f"{server.endpoint}/models/{model_id}", headers=headers)
                return MCPToolResult(success=True, result=resp.json())

        return MCPToolResult(success=False, error="Unknown HuggingFace tool")


# Global instance
mcp_manager = MCPManager()
