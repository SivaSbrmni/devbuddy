"""OpenAI-compatible provider base.

Groq, Cerebras, OpenRouter, GitHub Models, and Mistral all expose
OpenAI-compatible /chat/completions endpoints. This shared base handles
the common HTTP client logic, reducing per-provider code to just config.
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Optional

import httpx
import structlog

from app.llm.providers.base import BaseProvider, NormalizedResponse, ProviderConfig

log = structlog.get_logger()


class OpenAICompatProvider(BaseProvider):
    """Base for providers that implement the OpenAI chat completions API.

    Subclasses just set the base_url and default models in their ProviderConfig.
    """

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        if not self._api_key:
            raise RuntimeError(f"{self.name}: API key not configured")

        payload = self._build_payload(messages, model, max_tokens, temperature, system_prompt, stream=False)
        headers = self._build_headers()

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        latency = int((time.monotonic() - start) * 1000)
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        finish = choice.get("finish_reason", "stop")
        usage = data.get("usage", {})

        return NormalizedResponse(
            text=text,
            finish_reason=finish,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            provider=self.name,
            model=model,
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise RuntimeError(f"{self.name}: API key not configured")

        payload = self._build_payload(messages, model, max_tokens, temperature, system_prompt, stream=True)
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue

    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError(f"{self.name}: API key not configured")

        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.config.base_url}/embeddings",
                json={"input": texts, "model": model},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data.get("data", [])]

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str,
        stream: bool,
    ) -> dict[str, Any]:
        msgs = list(messages)
        if system_prompt:
            msgs = [{"role": "system", "content": system_prompt}] + msgs
        return {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
