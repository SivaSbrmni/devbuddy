"""GitHub Models provider — free dev-tier, used inside GHA runners."""

from __future__ import annotations

from app.llm.providers.base import ProviderConfig
from app.llm.providers.openai_compat import OpenAICompatProvider


class GitHubModelsProvider(OpenAICompatProvider):
    """GitHub Models — free dev-tier access to OpenAI/Llama models.

    Uses the GITHUB_TOKEN for auth, making it ideal for in-runner calls
    where the token is already available.
    """

    def __init__(self) -> None:
        super().__init__(ProviderConfig(
            name="github_models",
            models=[
                "gpt-4o-mini",
                "gpt-4o",
                "meta/Llama-3.3-70B-Instruct",
                "mistral-large",
            ],
            limits={"rpm": 20, "rpd": 100, "tpm": 8000},
            cooldown_on_error=60_000,
            api_key_env="GITHUB_TOKEN",
            base_url="https://models.inference.ai.azure.com",
        ))
