"""Prometheus Metrics — Phase 6.

Exposes application-level metrics for the AEP layer. These are
scraped by Prometheus and visualised in Grafana dashboards.

Spec reference: AGENTS.md Phase 6 — Observability, spec §11.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator, Optional

from app.aep.observability import aep_logger

_logger = aep_logger("aep.observability.metrics")


class Counter:
    """Thread-safe counter metric."""

    def __init__(self, name: str, description: str, labels: Optional[list[str]] = None) -> None:
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: dict[tuple[str, ...], float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, **labels: str) -> float:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        return self._values.get(key, 0.0)

    def collect(self) -> list[dict[str, Any]]:
        results = []
        for key, value in self._values.items():
            label_dict = dict(zip(self._labels, key))
            results.append({"labels": label_dict, "value": value})
        return results


class Histogram:
    """Simple histogram metric with predefined buckets."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[list[str]] = None,
        buckets: Optional[tuple[float, ...]] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._labels = labels or []
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._observations: dict[tuple[str, ...], list[float]] = {}

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        if key not in self._observations:
            self._observations[key] = []
        self._observations[key].append(value)

    @contextmanager
    def time(self, **labels: str) -> Generator[None, None, None]:
        start = time.monotonic()
        yield
        self.observe(time.monotonic() - start, **labels)

    def get_stats(self, **labels: str) -> dict[str, Any]:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        obs = self._observations.get(key, [])
        if not obs:
            return {"count": 0, "sum": 0.0, "avg": 0.0}
        return {
            "count": len(obs),
            "sum": sum(obs),
            "avg": sum(obs) / len(obs),
            "min": min(obs),
            "max": max(obs),
        }


class Gauge:
    """Thread-safe gauge metric."""

    def __init__(self, name: str, description: str, labels: Optional[list[str]] = None) -> None:
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: dict[tuple[str, ...], float] = {}

    def set(self, value: float, **labels: str) -> None:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        self._values[key] = value

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        self._values[key] = self._values.get(key, 0.0) - amount

    def get(self, **labels: str) -> float:
        key = tuple(labels.get(lbl, "") for lbl in self._labels)
        return self._values.get(key, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-defined AEP metrics
# ─────────────────────────────────────────────────────────────────────────────

# Execution metrics
executions_total = Counter(
    "aep_executions_total",
    "Total number of AEP task executions",
    labels=["tenant_id", "state"],
)

execution_duration_seconds = Histogram(
    "aep_execution_duration_seconds",
    "Duration of AEP task executions",
    labels=["tenant_id", "agent_name"],
)

active_executions = Gauge(
    "aep_active_executions",
    "Number of currently active AEP executions",
    labels=["tenant_id"],
)

# Agent metrics
agent_invocations_total = Counter(
    "aep_agent_invocations_total",
    "Total agent invocations",
    labels=["agent_name", "success"],
)

agent_duration_seconds = Histogram(
    "aep_agent_duration_seconds",
    "Duration of individual agent executions",
    labels=["agent_name"],
)

# LLM metrics
llm_requests_total = Counter(
    "aep_llm_requests_total",
    "Total LLM gateway requests",
    labels=["model", "purpose"],
)

llm_tokens_total = Counter(
    "aep_llm_tokens_total",
    "Total tokens consumed",
    labels=["model", "direction"],  # direction: "input" or "output"
)

llm_latency_seconds = Histogram(
    "aep_llm_latency_seconds",
    "LLM request latency",
    labels=["model"],
)

# Security metrics
security_violations_total = Counter(
    "aep_security_violations_total",
    "Total security violations detected",
    labels=["violation_type"],
)

rbac_denials_total = Counter(
    "aep_rbac_denials_total",
    "Total RBAC permission denials",
    labels=["role", "endpoint"],
)

# Webhook metrics
webhooks_received_total = Counter(
    "aep_webhooks_received_total",
    "Total GitHub webhooks received",
    labels=["event_type"],
)

# Memory metrics
memory_operations_total = Counter(
    "aep_memory_operations_total",
    "Total memory operations",
    labels=["operation"],  # store, recall, search, index
)


class MetricsRegistry:
    """Central registry for all AEP metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, Counter | Histogram | Gauge] = {
            "executions_total": executions_total,
            "execution_duration_seconds": execution_duration_seconds,
            "active_executions": active_executions,
            "agent_invocations_total": agent_invocations_total,
            "agent_duration_seconds": agent_duration_seconds,
            "llm_requests_total": llm_requests_total,
            "llm_tokens_total": llm_tokens_total,
            "llm_latency_seconds": llm_latency_seconds,
            "security_violations_total": security_violations_total,
            "rbac_denials_total": rbac_denials_total,
            "webhooks_received_total": webhooks_received_total,
            "memory_operations_total": memory_operations_total,
        }

    def get_all_metrics(self) -> dict[str, Any]:
        """Collect all metric values for the /metrics endpoint."""
        result: dict[str, Any] = {}
        for name, metric in self._metrics.items():
            if isinstance(metric, Counter):
                result[name] = metric.collect()
            elif isinstance(metric, Gauge):
                result[name] = {
                    "type": "gauge",
                    "values": dict(metric._values),
                }
            elif isinstance(metric, Histogram):
                result[name] = {
                    "type": "histogram",
                    "observations": {
                        str(k): len(v) for k, v in metric._observations.items()
                    },
                }
        return result


_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry
