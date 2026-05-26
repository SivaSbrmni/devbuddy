"""
Base :class:`AgentPlugin` abstract class.

Every autonomous agent (Planner, Coder, Debugger, …) implements this
interface. The plugin registry uses the class-level ``feature_flag``
attribute to decide whether an agent should be loaded at startup.

Spec reference: §3.4 (Plugin-Style Execution System), §6 (Agent System).

Phase 0 ships ONLY the base class — no concrete agent is registered
yet. Concrete agents land in Phase 3 (Planner, Coder) and Phase 5
(everyone else).
"""
from __future__ import annotations

import abc
from typing import ClassVar, Optional

from app.aep.plugins.types import AgentInput, AgentOutput


class AgentPlugin(abc.ABC):
    """ABC for an autonomous engineering agent.

    Subclasses MUST set the four class-level constants and implement
    :meth:`execute`. :meth:`health_check` defaults to ``True`` and may
    be overridden to probe external dependencies (LLM gateway, GitHub
    API, …).

    Subclasses are loaded into the registry at startup via
    :func:`app.aep.plugins.registry.PluginRegistry.discover`. A class
    whose :attr:`feature_flag` resolves to ``False`` is skipped.
    """

    #: Short identifier used for routing and logging (e.g. ``"planner"``).
    name: ClassVar[str] = ""

    #: Name of the feature flag that activates this agent. The flag must
    #: be registered in :data:`app.aep.feature_flags.FLAGS`.
    feature_flag: ClassVar[str] = ""

    #: Default model identifier (resolved through the LLM gateway router).
    model: ClassVar[str] = ""

    #: Optional fallback model identifier.
    fallback_model: ClassVar[Optional[str]] = None

    #: Human-readable description for the admin UI.
    description: ClassVar[str] = ""

    # ── Lifecycle ───────────────────────────────────────────────────────

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Allow abstract intermediate classes (those still containing
        # abstract methods) to skip the metadata check.
        if getattr(cls, "__abstractmethods__", None):
            return
        for required in ("name", "feature_flag", "model"):
            if not getattr(cls, required, ""):
                raise TypeError(
                    f"AgentPlugin subclass {cls.__name__!r} must set "
                    f"class attribute {required!r}"
                )

    # ── Abstract surface ────────────────────────────────────────────────

    @abc.abstractmethod
    async def execute(self, input: AgentInput) -> AgentOutput:
        """Run the agent against ``input`` and return its output."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Return ``True`` if the agent is ready to accept work.

        Default implementation always returns ``True``. Override to
        probe external dependencies (LLM gateway, GitHub API, …).
        """
        return True


__all__ = ["AgentPlugin"]
