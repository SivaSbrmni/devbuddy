"""
Concrete :class:`AgentPlugin` implementations.

Phase 0 ships **no agents**. Concrete agents land in Phase 3
(``planner.py``, ``coder.py``) and Phase 5 (everyone else).

The plugin registry discovers submodules of this package at startup
via :meth:`app.aep.plugins.registry.PluginRegistry.discover`, so
adding a new agent is as simple as dropping a new ``.py`` file here
that calls :meth:`PluginRegistry.register` (or uses the decorator) on
its agent class.
"""

__all__: list[str] = []
