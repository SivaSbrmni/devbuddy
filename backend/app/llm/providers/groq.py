"""Groq provider — Llama 3.3 70B, ~30 RPM / 1,000 RPD. Best for raw speed."""

from __future__ import annotations

from app.llm.providers.base import ProviderConfig
from app.llm.providers.openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    """Groq — ultra-low latency inference for Llama models."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="groq",
            models=[
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
            ],
            limits={"rpm": 30, "rpd": 1000, "tpm": 6000},
            cooldown_on_error=60_000,
            api_key_env="GROQ_API_KEY",
            base_url="https://api.groq.com/openai/v1",
        ))
