"""Tests for the GitHub client factory and auth implementations."""
import os
from unittest.mock import patch

import pytest

from app.aep.github.client import (
    OAuthClient,
    PersonalAccessTokenClient,
    get_github_client,
    reset_github_client,
)


class TestPersonalAccessTokenClient:
    """PAT client auth headers."""

    @pytest.mark.asyncio
    async def test_auth_headers(self) -> None:
        client = PersonalAccessTokenClient("ghp_test123")
        headers = await client._auth_headers()
        assert headers == {"Authorization": "token ghp_test123"}


class TestGetGitHubClient:
    """Factory function for the GitHub client singleton."""

    def setup_method(self) -> None:
        reset_github_client()

    def teardown_method(self) -> None:
        reset_github_client()

    def test_pat_from_env(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
            client = get_github_client()
            assert isinstance(client, PersonalAccessTokenClient)

    def test_gh_token_fallback(self) -> None:
        env = {"GH_TOKEN": "ghp_test2"}
        with patch.dict(os.environ, env, clear=False):
            # Remove GITHUB_TOKEN if set
            os.environ.pop("GITHUB_TOKEN", None)
            reset_github_client()
            client = get_github_client()
            assert isinstance(client, PersonalAccessTokenClient)

    def test_no_credentials_raises(self) -> None:
        env_clean = {
            k: v for k, v in os.environ.items()
            if k not in {"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_INSTALLATION_ID"}
        }
        with patch.dict(os.environ, env_clean, clear=True):
            reset_github_client()
            with pytest.raises(RuntimeError, match="No GitHub credentials"):
                get_github_client()

    def test_singleton_reuse(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
            c1 = get_github_client()
            c2 = get_github_client()
            assert c1 is c2


class TestOAuthClient:
    """OAuth client auth headers."""

    @pytest.mark.asyncio
    async def test_auth_headers_bearer(self) -> None:
        client = OAuthClient("gho_abc123xyz")
        headers = await client._auth_headers()
        assert headers == {"Authorization": "Bearer gho_abc123xyz"}

    @pytest.mark.asyncio
    async def test_different_tokens_produce_different_headers(self) -> None:
        c1 = OAuthClient("token_a")
        c2 = OAuthClient("token_b")
        h1 = await c1._auth_headers()
        h2 = await c2._auth_headers()
        assert h1 != h2
        assert "token_a" in h1["Authorization"]
        assert "token_b" in h2["Authorization"]
