"""Structured exception hierarchy for the AEP LLM gateway.

Every failure that could plausibly be returned to a gateway caller is
mapped to one of these types so the HTTP layer can translate them to a
consistent error envelope with the right status code.
"""
from __future__ import annotations

from typing import Any, Optional


class LlmGatewayError(Exception):
    """Base class for every gateway-originated failure."""

    http_status: int = 502
    error_code: str = "gateway_error"

    def __init__(
        self,
        message: str,
        *,
        upstream_status: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.upstream_status = upstream_status
        self.details = details or {}

    def to_envelope(self) -> dict[str, Any]:
        env: dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.upstream_status is not None:
            env["upstream_status"] = self.upstream_status
        if self.details:
            env["details"] = self.details
        return env


class UpstreamUnavailable(LlmGatewayError):
    """Ollama could not be reached (network / DNS / refused)."""

    http_status = 502
    error_code = "upstream_unavailable"


class UpstreamTimeout(LlmGatewayError):
    """Ollama did not respond in time."""

    http_status = 504
    error_code = "upstream_timeout"


class UpstreamHttpError(LlmGatewayError):
    """Ollama returned a non-2xx response."""

    http_status = 502
    error_code = "upstream_http_error"


class ModelNotFound(LlmGatewayError):
    """The requested model is not loaded on the upstream."""

    http_status = 404
    error_code = "model_not_found"


class InvalidRequest(LlmGatewayError):
    """The caller's payload was rejected before reaching Ollama."""

    http_status = 400
    error_code = "invalid_request"


__all__ = [
    "LlmGatewayError",
    "UpstreamUnavailable",
    "UpstreamTimeout",
    "UpstreamHttpError",
    "ModelNotFound",
    "InvalidRequest",
]
