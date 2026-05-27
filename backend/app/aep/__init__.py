"""
AEP — Autonomous Engineering Platform (Phase 0 foundation).

Per the AEP implementation specification, this package implements the
capability layer that attaches to the existing DevBuddy application
through clearly defined extension points. Nothing in this package is
allowed to modify the existing service contracts destructively.

In Phase 0 every public surface is wired but **dormant** — feature
flags default to ``False`` and routes return structured 503 envelopes
so the codebase can be merged without behavior change.

Subpackages:
    :mod:`app.aep.api`        — FastAPI routers (``/LLM/*`` and
                                ``/api/v1/aep/flags``).
    :mod:`app.aep.compat`     — Compatibility Adapter Layer that
                                wraps existing services with no-op hooks.
    :mod:`app.aep.plugins`    — Plugin registry and the
                                :class:`AgentPlugin` ABC.
    :mod:`app.aep.feature_flags` — :class:`FeatureFlagService`.
    :mod:`app.aep.models`     — SQLAlchemy models for ``aep_*`` tables.
    :mod:`app.aep.observability` — Structured logging / metric helpers.

See ``EXTENSIONS.md`` at the repo root for the full extension-point catalogue.
"""

__all__: list[str] = [
    "feature_flags",
    "compat",
    "plugins",
    "api",
    "models",
    "observability",
]
