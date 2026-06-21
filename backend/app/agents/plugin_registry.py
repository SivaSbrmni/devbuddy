"""Plugin registry + AgentPlugin interface — spec Part 1.

All agents implement the AgentPlugin interface, allowing them to be
registered, discovered, and orchestrated by the Coordinator.

Feature flags gate which plugins are active. When a flag is disabled,
the plugin is registered but can_handle() returns False.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

log = structlog.get_logger()


@dataclass
class Task:
    """A unit of work for an agent."""
    id: str
    title: str
    description: str
    task_type: str  # planner, coder, debugger, reviewer, test, security, docs, devops
    repository: Optional[dict] = None
    branch: Optional[str] = None
    context: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of an agent execution."""
    success: bool
    output: str = ""
    artifacts: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    tokens_used: dict = field(default_factory=dict)
    provider_used: str = ""


@dataclass
class AgentError:
    """Error from an agent execution."""
    message: str
    code: str = "agent_error"
    retryable: bool = False
    context: dict = field(default_factory=dict)


@dataclass
class PlatformContext:
    """Platform context provided to plugins during initialization."""
    tenant_id: str = "default"
    feature_flags: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Execution context provided to plugins during execution."""
    task: Task
    github_token: Optional[str] = None
    branch: Optional[str] = None
    workspace_path: Optional[str] = None
    llm_gateway: Any = None  # LLMGateway instance
    memory: Any = None  # ContextEngine instance


class AgentCapability:
    """Capability descriptor for an agent plugin."""
    PLANNING = "planning"
    CODING = "coding"
    DEBUGGING = "debugging"
    REVIEWING = "reviewing"
    TESTING = "testing"
    SECURITY = "security"
    DOCS = "docs"
    DEVOPS = "devops"
    COORDINATION = "coordination"


class AgentPlugin(ABC):
    """Plugin contract for all agents (spec Part 1).

    Every agent implements this interface, allowing the Coordinator
    to discover, select, and orchestrate them.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of capabilities this plugin provides."""
        ...

    @abstractmethod
    async def initialize(self, ctx: PlatformContext) -> None:
        """Initialize the plugin with platform context."""
        ...

    @abstractmethod
    def can_handle(self, task: Task) -> bool:
        """Check if this plugin can handle the given task."""
        ...

    @abstractmethod
    async def execute(self, task: Task, ctx: ExecutionContext) -> AgentResult:
        """Execute the task."""
        ...

    async def on_success(self, result: AgentResult) -> None:
        """Called after successful execution. Override for custom behavior."""
        pass

    async def on_failure(self, error: AgentError) -> None:
        """Called after failed execution. Override for custom behavior."""
        pass

    async def shutdown(self) -> None:
        """Clean up resources. Override for custom behavior."""
        pass


class PluginRegistry:
    """Registry for agent plugins.

    Plugins are registered at startup and discovered by capability.
    Feature flags gate which plugins are active.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, AgentPlugin] = {}
        self._initialized = False

    def register(self, plugin: AgentPlugin) -> None:
        """Register a plugin."""
        self._plugins[plugin.name] = plugin
        log.info("plugin.registered", name=plugin.name, version=plugin.version, capabilities=plugin.capabilities)

    def unregister(self, name: str) -> None:
        """Unregister a plugin."""
        if name in self._plugins:
            self._plugins.pop(name)
            log.info("plugin.unregistered", name=name)

    def get(self, name: str) -> Optional[AgentPlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        """List all registered plugins."""
        return [
            {"name": p.name, "version": p.version, "capabilities": p.capabilities}
            for p in self._plugins.values()
        ]

    def find_by_capability(self, capability: str) -> list[AgentPlugin]:
        """Find all plugins with a given capability."""
        return [p for p in self._plugins.values() if capability in p.capabilities]

    def find_for_task(self, task: Task) -> Optional[AgentPlugin]:
        """Find the best plugin for a task."""
        # Map task types to capabilities
        capability_map = {
            "planner": AgentCapability.PLANNING,
            "coder": AgentCapability.CODING,
            "debugger": AgentCapability.DEBUGGING,
            "reviewer": AgentCapability.REVIEWING,
            "test": AgentCapability.TESTING,
            "security": AgentCapability.SECURITY,
            "docs": AgentCapability.DOCS,
            "devops": AgentCapability.DEVOPS,
        }
        capability = capability_map.get(task.task_type)
        if not capability:
            return None

        plugins = self.find_by_capability(capability)
        for plugin in plugins:
            if plugin.can_handle(task):
                return plugin
        return None

    async def initialize_all(self, ctx: PlatformContext) -> None:
        """Initialize all registered plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.initialize(ctx)
            except Exception as e:
                log.error("plugin.init_failed", name=plugin.name, error=str(e))
        self._initialized = True

    async def shutdown_all(self) -> None:
        """Shut down all registered plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                log.error("plugin.shutdown_failed", name=plugin.name, error=str(e))


# Singleton
plugin_registry = PluginRegistry()
