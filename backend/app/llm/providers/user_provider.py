"""User-configured provider adapter.

Wraps a UserLLMProvider record (from the existing universal provider config)
and exposes it through the BaseProvider interface. No hardcoded API keys;
all credentials come from the user's encrypted provider configuration.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx
import structlog

from app.core.crypto import decrypt_value
from app.llm.providers.base import BaseProvider, NormalizedResponse, ProviderConfig

log = structlog.get_logger()


class UserProviderAdapter(BaseProvider):
    """Adapter that routes LLM calls through a user-configured provider.

    Supports provider_type values from the existing UserLLMProvider table:
      - openai-compatible (OpenRouter, Groq, Cerebras, Mistral, Azure, custom)
      - anthropic
      - ollama
      - google (Gemini, via OpenAI-compatible endpoint)
    """

    def __init__(self, provider_record: Any) -> None:
        """Wrap a UserLLMProvider ORM record."""
        # Import here to avoid circular imports at module load
        from app.models.llm_provider import UserLLMProvider

        if not isinstance(provider_record, UserLLMProvider):
            raise TypeError("UserProviderAdapter expects a UserLLMProvider record")

        self.record = provider_record
        self.provider_id = str(provider_record.id)
        self.provider_type = (provider_record.provider_type or "openai-compatible").lower()

        # Decrypt API key from the existing encrypted storage
        encrypted_key = provider_record.api_key_encrypted or ""
        self._api_key = decrypt_value(encrypted_key) if encrypted_key else ""

        # Normalize base URL. For Ollama, users often paste the /api endpoint,
        # so strip that suffix to keep the conventional base URL.
        base_url = provider_record.base_url.rstrip("/")
        if self.provider_type == "ollama" and base_url.endswith("/api"):
            base_url = base_url[:-4]

        # Build a ProviderConfig from the record
        models = list(provider_record.available_models or [provider_record.default_model])
        config = ProviderConfig(
            name=provider_record.name,
            models=models,
            limits={"rpm": 60, "rpd": 1000, "tpm": 10000},  # safe defaults
            cooldown_on_error=60_000,
            api_key_env="",  # key is loaded directly from the record
            base_url=base_url,
        )
        super().__init__(config)

        self._client: httpx.AsyncClient | None = None
        self._supports_streaming = bool(provider_record.supports_streaming)
        self._supports_tools = bool(provider_record.supports_tools)
        self._max_tokens = int(provider_record.max_tokens or 4096)
        self._headers = dict(provider_record.headers or {})

    def is_configured(self) -> bool:
        """A provider is configured if it has a key, auth headers, or is a local Ollama."""
        if self._api_key:
            return True
        # Some providers (e.g., Azure OpenAI) use custom auth headers.
        auth_headers = {"authorization", "x-api-key", "api-key"}
        if any(h.lower() in auth_headers for h in self._headers):
            return True
        # Local Ollama instances do not require an API key.
        if self.provider_type == "ollama":
            base = self.config.base_url.lower()
            if "localhost" in base or "127.0.0.1" in base:
                return True
        return False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = self._headers.copy()
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            headers["Content-Type"] = "application/json"
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=120.0,
            )
        return self._client

    async def _close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_messages(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> list[dict[str, str]]:
        out = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        out.extend(messages)
        return out

    def _resolve_model(self, model: str | None) -> str:
        return model or self.record.default_model

    def _parse_openai_response(self, data: dict, latency_ms: int) -> NormalizedResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})
        return NormalizedResponse(
            text=content,
            finish_reason=choice.get("finish_reason", "stop"),
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            provider=self.name,
            model=data.get("model", self.record.default_model),
            latency_ms=latency_ms,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        """Non-streaming chat completion."""
        resolved_model = self._resolve_model(model)

        if self.provider_type == "anthropic":
            return await self._chat_anthropic(messages, resolved_model, max_tokens, temperature, system_prompt)
        if self.provider_type == "ollama":
            return await self._chat_ollama(messages, resolved_model, max_tokens, temperature, system_prompt)
        return await self._chat_openai(messages, resolved_model, max_tokens, temperature, system_prompt)

    async def _chat_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> NormalizedResponse:
        start = time.monotonic()
        client = self._get_client()
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": min(max_tokens, self._max_tokens),
            "temperature": temperature,
        }
        resp = await client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        return self._parse_openai_response(data, latency_ms)

    async def _chat_anthropic(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> NormalizedResponse:
        start = time.monotonic()
        client = self._get_client()
        # Anthropic native API uses x-api-key header
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": min(max_tokens, self._max_tokens),
            "messages": messages,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        resp = await client.post("/v1/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        content = ""
        if data.get("content"):
            content = data["content"][0].get("text", "")
        usage = data.get("usage", {})
        return NormalizedResponse(
            text=content,
            finish_reason=data.get("stop_reason", "stop"),
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
        )

    async def _chat_ollama(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> NormalizedResponse:
        start = time.monotonic()
        client = self._get_client()
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "stream": False,
            "options": {
                "num_predict": min(max_tokens, self._max_tokens),
                "temperature": temperature,
            },
        }
        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        content = data.get("message", {}).get("content", "")
        return NormalizedResponse(
            text=content,
            finish_reason="stop",
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        """Streaming chat completion — yields text deltas."""
        if not self._supports_streaming:
            # Fall back to non-streaming and yield the whole text
            resp = await self.chat(messages, model, max_tokens, temperature, system_prompt)
            yield resp.text
            return

        resolved_model = self._resolve_model(model)
        if self.provider_type == "anthropic":
            async for delta in self._stream_anthropic(messages, resolved_model, max_tokens, temperature, system_prompt):
                yield delta
            return
        if self.provider_type == "ollama":
            async for delta in self._stream_ollama(messages, resolved_model, max_tokens, temperature, system_prompt):
                yield delta
            return
        async for delta in self._stream_openai(messages, resolved_model, max_tokens, temperature, system_prompt):
            yield delta

    async def _stream_openai(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        log.info("user_provider.stream_openai", provider=self.name, base_url=self.config.base_url, model=model)
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "max_tokens": min(max_tokens, self._max_tokens),
            "temperature": temperature,
            "stream": True,
        }
        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue

    async def _stream_anthropic(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": min(max_tokens, self._max_tokens),
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        async with client.stream("POST", "/v1/messages", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "content_block_delta":
                        text = data.get("delta", {}).get("text", "")
                        if text:
                            yield text
                except json.JSONDecodeError:
                    continue

    async def _stream_ollama(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        log.info("user_provider.stream_ollama", provider=self.name, base_url=self.config.base_url, model=model)
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "stream": True,
            "options": {
                "num_predict": min(max_tokens, self._max_tokens),
                "temperature": temperature,
            },
        }
        async with client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        """Text embeddings via OpenAI-compatible /embeddings endpoint."""
        client = self._get_client()
        resolved_model = self._resolve_model(model)
        try:
            resp = await client.post(
                "/embeddings",
                json={"model": resolved_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item.get("embedding", []) for item in data.get("data", [])]
        except Exception as e:
            log.warning("user_provider.embeddings_failed", provider=self.name, error=str(e))
            return []

    async def test_connection(self) -> dict:
        """Test the provider connection and measure latency."""
        start = time.monotonic()
        try:
            client = self._get_client()
            if self.provider_type == "ollama":
                resp = await client.get("/api/tags")
            else:
                # OpenAI-compatible /models endpoint
                resp = await client.get("/models")
            resp.raise_for_status()
            latency_ms = int((time.monotonic() - start) * 1000)
            data = resp.json()
            if self.provider_type == "ollama":
                models = [m.get("name", "") for m in data.get("models", [])]
            else:
                models = [m.get("id", "") for m in data.get("data", [])]
            return {
                "success": True,
                "latency_ms": latency_ms,
                "models": models,
                "message": f"Connected. {len(models)} models available.",
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "models": [],
                "message": str(e),
            }
