"""OpenRouter provider — 28+ free models, universal fallback net."""

from __future__ import annotations

from app.llm.providers.base import ProviderConfig
from app.llm.providers.openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    """OpenRouter — free pool with DeepSeek R1, Qwen3 Coder, and many more."""

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="openrouter",
            models=[
                "deepseek/deepseek-r1",
                "qwen/qwen3-coder-480b",
                "meta-llama/llama-3.3-70b-instruct",
                "google/gemini-2.5-flash-preview",
                "mistralai/mistral-small-3.1-24b-instruct:free",
            ],
            limits={"rpm": 20, "rpd": 200, "tpm": 10000},
            cooldown_on_error=60_000,
            api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
        ))

    def _build_headers(self) -> dict[str, str]:
        """OpenRouter requires HTTP-Referer and X-Title headers."""
        headers = super()._build_headers()
        headers["HTTP-Referer"] = "https://devbuddy.org"
        headers["X-Title"] = "DevBuddy Autonomous Engineering Platform"
        return headers
