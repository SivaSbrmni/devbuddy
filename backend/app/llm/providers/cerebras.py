"""Cerebras provider — Llama 3.3 70B, ~1M tokens/day, high throughput."""

from __future__ import annotations

from app.llm.providers.base import ProviderConfig
from app.llm.providers.openai_compat import OpenAICompatProvider


class CerebrasProvider(OpenAICompatProvider):
    """Cerebras — high-throughput inference for Llama models."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="cerebras",
            models=[
                "llama-3.3-70b",
                "llama-3.1-8b",
            ],
            limits={"rpm": 60, "rpd": 0, "tpm": 100000},  # 1M tokens/day
            cooldown_on_error=60_000,
            api_key_env="CEREBRAS_API_KEY",
            base_url="https://api.cerebras.ai/v1",
        ))
