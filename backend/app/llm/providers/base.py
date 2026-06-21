"""Base provider interface for the LLM Gateway.

Every provider implements this interface. The gateway calls providers
through this abstraction, never directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import structlog

log = structlog.get_logger()


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    models: list[str]
    limits: dict[str, int] = field(default_factory=dict)  # rpm, rpd, tpm
    cooldown_on_error: int = 60_000  # ms, exponential backoff base
    api_key_env: str = ""  # environment variable name for API key
    base_url: str = ""


@dataclass
class NormalizedResponse:
    """Normalized response — every downstream consumer sees this shape only."""
    text: str
    finish_reason: str = "stop"  # stop, length, tool_call, error
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    provider: str = ""
    model: str = ""
    latency_ms: int = 0


class BaseProvider(ABC):
    """Abstract base class for all LLM providers.

    Providers are responsible for:
    1. Translating normalized requests to their native API format
    2. Calling their API (with proper auth headers)
    3. Returning a NormalizedResponse
    4. Streaming via async iterator when requested
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.name = config.name
        self._api_key: Optional[str] = None

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        """Non-streaming chat completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        """Streaming chat completion — yields text deltas."""
        ...

    @abstractmethod
    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        """Text embeddings."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Check if the provider is reachable and configured."""
        return {
            "ok": self._api_key is not None,
            "name": self.name,
            "models": self.config.models,
            "configured": self._api_key is not None,
        }

    def configure(self, api_key: str) -> None:
        """Set the API key for this provider."""
        self._api_key = api_key

    def is_configured(self) -> bool:
        """Check if this provider has credentials."""
        return self._api_key is not None

    def supports_model(self, model: str) -> bool:
        """Check if this provider serves the given model."""
        return model in self.config.models

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} configured={self.is_configured()}>"
