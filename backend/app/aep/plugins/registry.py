"""
Plugin registry for :class:`AgentPlugin` subclasses.

The registry is the single point of truth for which agents are
*active* in the current process. An agent class becomes active when:

    1. Its module is imported (which triggers
       :meth:`PluginRegistry.register` via the decorator) AND
    2. Its :attr:`AgentPlugin.feature_flag` resolves to ``True``
       through the :class:`FeatureFlagService`.

:meth:`PluginRegistry.discover` is invoked from the FastAPI lifespan
hook; it walks the :mod:`app.aep.plugins.agents` namespace and imports
every submodule. Submodules that fail to import — for example because
an optional dependency is missing — are skipped with a warning rather
than crashing the host application.

In Phase 0 the ``agents/`` package is empty, so :meth:`discover`
finds nothing and the registry stays empty. That's intentional.
"""
from __future__ import annotations

import importlib
import pkgutil
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.aep.feature_flags import FeatureFlagService, get_feature_flag_service
from app.aep.plugins.base import AgentPlugin

logger = get_logger("aep.plugins.registry")


class PluginRegistry:
    """Stores active :class:`AgentPlugin` instances indexed by name."""

    def __init__(
        self,
        feature_flag_service: Optional[FeatureFlagService] = None,
    ) -> None:
        self._ff = feature_flag_service or get_feature_flag_service()
        # Registered classes (regardless of flag state).
        self._classes: dict[str, type[AgentPlugin]] = {}
        # Active instances (only those whose flag is enabled).
        self._instances: dict[str, AgentPlugin] = {}

    # ── Registration ────────────────────────────────────────────────────

    def register(self, cls: type[AgentPlugin]) -> type[AgentPlugin]:
        """Class decorator that registers an :class:`AgentPlugin`.

        Registration does NOT activate the agent. The agent only goes
        active during :meth:`discover` if its feature flag resolves to
        ``True``.

        Re-registering the same name overrides the previous class
        (useful for hot-reload in development).
        """
        if not issubclass(cls, AgentPlugin):
            raise TypeError(f"{cls!r} is not an AgentPlugin subclass")
        if not cls.name:
            raise ValueError(f"AgentPlugin subclass {cls!r} has no .name set")
        previous = self._classes.get(cls.name)
        if previous is not None and previous is not cls:
            logger.warning(
                "plugin_overriding_previous",
                name=cls.name,
                previous=previous.__name__,
                current=cls.__name__,
            )
        self._classes[cls.name] = cls
        logger.debug("plugin_registered", name=cls.name, cls=cls.__name__)
        return cls

    # ── Discovery / activation ─────────────────────────────────────────

    async def discover(
        self,
        *,
        package: str = "app.aep.plugins.agents",
        tenant_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[str]:
        """Import every submodule of ``package`` and activate flagged agents.

        Returns the list of agent names that became active.
        """
        try:
            pkg = importlib.import_module(package)
        except ImportError as exc:
            logger.warning("plugin_package_missing", package=package, error=str(exc))
            return []

        # Walk the package and import every submodule, triggering
        # decorator-driven registration as a side effect.
        for module_info in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
            module_name = f"{package}.{module_info.name}"
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "plugin_import_failed",
                    module=module_name,
                    error=str(exc),
                )

        return await self.activate_registered(tenant_id=tenant_id, db=db)

    async def activate_registered(
        self,
        *,
        tenant_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[str]:
        """Instantiate every registered class whose flag is enabled."""
        active: list[str] = []
        for name, cls in self._classes.items():
            try:
                enabled = await self._ff.is_enabled(
                    cls.feature_flag, tenant_id=tenant_id, db=db
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "plugin_flag_resolution_failed",
                    name=name,
                    flag=cls.feature_flag,
                    error=str(exc),
                )
                enabled = False
            if not enabled:
                self._instances.pop(name, None)
                continue
            if name not in self._instances:
                try:
                    self._instances[name] = cls()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "plugin_instantiation_failed",
                        name=name,
                        error=str(exc),
                    )
                    continue
            active.append(name)
        logger.info("plugins_activated", names=active, total_registered=len(self._classes))
        return active

    # ── Lookup ──────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[AgentPlugin]:
        """Return the active instance for ``name`` or ``None``."""
        return self._instances.get(name)

    def get_class(self, name: str) -> Optional[type[AgentPlugin]]:
        """Return the registered class for ``name`` or ``None``."""
        return self._classes.get(name)

    def list_active(self) -> list[AgentPlugin]:
        """Return a snapshot of currently active plugin instances."""
        return list(self._instances.values())

    def list_registered(self) -> list[type[AgentPlugin]]:
        """Return every registered :class:`AgentPlugin` class."""
        return list(self._classes.values())

    def info(self) -> list[dict[str, Any]]:
        """Return diagnostic info about every registered plugin."""
        out: list[dict[str, Any]] = []
        for name, cls in self._classes.items():
            out.append(
                {
                    "name": name,
                    "class": f"{cls.__module__}.{cls.__name__}",
                    "feature_flag": cls.feature_flag,
                    "model": cls.model,
                    "fallback_model": cls.fallback_model,
                    "active": name in self._instances,
                    "description": cls.description,
                }
            )
        return out

    def clear(self) -> None:
        """Drop every registered class and active instance. Test-only."""
        self._classes.clear()
        self._instances.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────


_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """Return the application-wide :class:`PluginRegistry`."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    """Reset the singleton. Test-only helper."""
    global _registry
    _registry = None


__all__ = [
    "PluginRegistry",
    "get_plugin_registry",
    "reset_plugin_registry",
]
