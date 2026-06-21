"""Google AI Studio (Gemini) provider — huge context (1M tokens), free tier.

Uses Google's native Generative AI API (not OpenAI-compatible).
Best for: huge-context calls (full repo dumps), reviewer tasks.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx
import structlog

from app.llm.providers.base import BaseProvider, NormalizedResponse, ProviderConfig

log = structlog.get_logger()


class GeminiProvider(BaseProvider):
    """Google AI Studio — Gemini 2.5 Flash with 1M token context window."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="gemini",
            models=[
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "text-embedding-004",
            ],
            limits={"rpm": 15, "rpd": 1500, "tpm": 1000000},
            cooldown_on_error=60_000,
            api_key_env="GEMINI_API_KEY",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        ))

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        system_prompt: str = "",
    ) -> NormalizedResponse:
        if not self._api_key:
            raise RuntimeError("gemini: API key not configured")

        contents = self._convert_messages(messages)
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"{self.config.base_url}/models/{model}:generateContent?key={self._api_key}"
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        latency = int((time.monotonic() - start) * 1000)
        candidates = data.get("candidates", [])
        text = ""
        finish = "stop"
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            finish = candidates[0].get("finishReason", "stop").lower()

        usage_meta = data.get("usageMetadata", {})
        return NormalizedResponse(
            text=text,
            finish_reason=finish,
            usage={
                "input_tokens": usage_meta.get("promptTokenCount", 0),
                "output_tokens": usage_meta.get("candidatesTokenCount", 0),
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
            raise RuntimeError("gemini: API key not configured")

        contents = self._convert_messages(messages)
        body = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"{self.config.base_url}/models/{model}:streamGenerateContent?key={self._api_key}&alt=sse"
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        for p in parts:
                            t = p.get("text", "")
                            if t:
                                yield t
                    except Exception:
                        continue

    async def embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError("gemini: API key not configured")

        url = f"{self.config.base_url}/models/{model}:batchEmbedContents?key={self._api_key}"
        body = {
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
                for t in texts
            ]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            return [e["values"] for e in data.get("embeddings", [])]

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Convert OpenAI-style messages to Gemini's contents format."""
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            gemini_role = "user" if role == "user" else "model"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg.get("content", "")}],
            })
        return contents
