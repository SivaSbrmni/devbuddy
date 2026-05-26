"""
AEP-specific observability helpers.

Phase 0 only needs structured-logging wrappers; metrics + tracing are
wired in Phase 6 once Prometheus/OpenTelemetry land in the stack.

Every helper here is a thin shim over :func:`app.core.logger.get_logger`
so the existing structlog pipeline already routes AEP events to Loki
through the existing promtail config.

The helpers add a stable ``component`` field and an ``aep`` namespace
to every event so dashboards can filter cleanly.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.core.logger import get_logger

_BASE_LOGGER = get_logger("aep")


def aep_logger(component: str) -> structlog.BoundLogger:
    """Return a structlog logger bound to an AEP ``component`` value."""
    return _BASE_LOGGER.bind(aep_component=component)


def emit_event(component: str, event: str, **fields: Any) -> None:
    """Emit a single structured event under the AEP namespace.

    This is a convenience wrapper for components that don't want to
    keep a logger reference around. It always logs at INFO level.
    """
    aep_logger(component).info(event, **fields)


__all__ = ["aep_logger", "emit_event"]
