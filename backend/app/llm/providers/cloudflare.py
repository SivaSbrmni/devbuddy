"""Cloudflare Workers AI provider — small models, ~10K neurons/day.

Best for: trivial calls (formatting, classification, simple summaries).
Uses Cloudflare's REST API for Workers AI.
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator

import httpx

from app.llm.providers.base import BaseProvider, NormalizedResponse, ProviderConfig


class CloudflareProvider(BaseProvider):
    """Cloudflare Workers AI — small open models for trivial tasks."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="cloudflare",
            models=[
                "@cf/meta/llama-3.1-8b-instruct",
                "@cf/qwen/qwen2.5-coder-32b-instruct",
            ],
            limits={"rpm": 50, "rpd": 10000, "tpm": 50000},
            cooldown_on_error=60_000,
            api_key_env="CLOUDFLARE_API_TOKEN",
            base_url="https://api.cloudflare.com/client/v4/accounts",
        ))
        self._account_id_env = "CLOUDFLARE_ACCOUNT_ID"

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        if not self._api_key:
            raise RuntimeError("cloudflare: API token not configured")

        import os
        account_id = os.environ.get(self._account_id_env, "")
        if not account_id:
            raise RuntimeError("cloudflare: account ID not configured")

        msgs = list(messages)
        if system_prompt:
            msgs = [{"role": "system", "content": system_prompt}] + msgs

        url = f"{self.config.base_url}/{account_id}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        body = {
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        latency = int((time.monotonic() - start) * 1000)
        result = data.get("result", {})
        text = result.get("response", "")
        usage = result.get("usage", {})

        return NormalizedResponse(
            text=text,
            finish_reason="stop",
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
        # Cloudflare Workers AI supports SSE streaming via ?stream=true
        # For simplicity, fall back to non-streaming and yield the full text
        resp = await self.chat(messages, model, max_tokens, temperature, system_prompt)
        yield resp.text

    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError("cloudflare: API token not configured")

        import os
        account_id = os.environ.get(self._account_id_env, "")
        url = f"{self.config.base_url}/{account_id}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        results = []
        async with httpx.AsyncClient(timeout=60) as client:
            for text in texts:
                resp = await client.post(url, json={"text": [text]}, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                results.append(data.get("result", {}).get("data", [0])[0])
        return results
