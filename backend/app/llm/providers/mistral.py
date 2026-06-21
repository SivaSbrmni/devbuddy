"""Mistral provider — free prototyping tier, lightweight docs/summaries."""

from __future__ import annotations

from app.llm.providers.base import ProviderConfig
from app.llm.providers.openai_compat import OpenAICompatProvider


class MistralProvider(OpenAICompatProvider):
    """Mistral — free tier for lightweight documentation and summaries."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="mistral",
            models=[
                "mistral-small-latest",
                "open-mistral-7b",
            ],
            limits={"rpm": 50, "rpd": 500, "tpm": 30000},
            cooldown_on_error=60_000,
            api_key_env="MISTRAL_API_KEY",
            base_url="https://api.mistral.ai/v1",
        ))
