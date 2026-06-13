"""OpenTelemetry Tracing — Phase 6.

Distributed tracing propagated through:
    API → Orchestrator → Agent → LLM Gateway → Ollama

Spec reference: AGENTS.md Phase 6 — Observability, spec §11.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Generator, Optional

from app.aep.observability import aep_logger

_logger = aep_logger("aep.observability.tracing")


class Span:
    """Lightweight span representation for distributed tracing."""

    def __init__(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        operation: str,
        service: str = "aep",
        attributes: Optional[dict[str, Any]] = None,
    ) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.operation = operation
        self.service = service
        self.attributes = attributes or {}
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.status: str = "ok"
        self.events: list[dict[str, Any]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_status(self, status: str, description: Optional[str] = None) -> None:
        self.status = status
        if description:
            self.set_attribute("status_description", description)

    def end(self) -> None:
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "service": self.service,
            "attributes": self.attributes,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "events": self.events,
        }


class TraceContext:
    """Propagated trace context (W3C Trace Context compatible)."""

    def __init__(
        self,
        *,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.parent_span_id = parent_span_id

    def create_span(self, operation: str, **attributes: Any) -> Span:
        span = Span(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.parent_span_id,
            operation=operation,
            attributes=attributes,
        )
        return span

    def child_context(self, span: Span) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            parent_span_id=span.span_id,
        )

    def to_headers(self) -> dict[str, str]:
        """Generate W3C traceparent header."""
        parent = self.parent_span_id or "0000000000000000"
        return {
            "traceparent": f"00-{self.trace_id}-{parent}-01",
        }

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> TraceContext:
        """Parse W3C traceparent header."""
        traceparent = headers.get("traceparent", "")
        parts = traceparent.split("-")
        if len(parts) >= 3:
            return cls(trace_id=parts[1], parent_span_id=parts[2])
        return cls()


class Tracer:
    """Simple tracer that collects spans for export."""

    def __init__(self, service_name: str = "aep") -> None:
        self._service = service_name
        self._spans: list[Span] = []
        self._max_spans = 10000

    @contextmanager
    def start_span(
        self,
        operation: str,
        *,
        context: Optional[TraceContext] = None,
        **attributes: Any,
    ) -> Generator[Span, None, None]:
        ctx = context or TraceContext()
        span = ctx.create_span(operation, **attributes)
        span.service = self._service
        try:
            yield span
        except Exception as exc:
            span.set_status("error", str(exc))
            raise
        finally:
            span.end()
            self._record(span)

    @asynccontextmanager
    async def start_async_span(
        self,
        operation: str,
        *,
        context: Optional[TraceContext] = None,
        **attributes: Any,
    ) -> AsyncGenerator[Span, None]:
        ctx = context or TraceContext()
        span = ctx.create_span(operation, **attributes)
        span.service = self._service
        try:
            yield span
        except Exception as exc:
            span.set_status("error", str(exc))
            raise
        finally:
            span.end()
            self._record(span)

    def _record(self, span: Span) -> None:
        if len(self._spans) >= self._max_spans:
            self._spans = self._spans[-self._max_spans // 2:]
        self._spans.append(span)

        _logger.debug(
            "span_completed",
            trace_id=span.trace_id,
            span_id=span.span_id,
            operation=span.operation,
            duration_ms=span.duration_ms,
            status=span.status,
        )

    def get_recent_spans(self, limit: int = 100) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._spans[-limit:]]

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._spans if s.trace_id == trace_id]


_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
