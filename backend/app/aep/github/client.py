"""Abstract GitHub client + concrete implementations.

Spec reference: AGENTS.md Phase 2 — GitHub integration.

Two concrete implementations:

* :class:`PersonalAccessTokenClient` — simplest auth; a classic PAT in
  the ``Authorization: token <PAT>`` header. Good for local dev and
  single-user setups.
* :class:`GitHubAppClient` — GitHub App installation tokens.  Higher
  rate limits (5 000 req/hr per installation) and fine-grained
  permissions.  Requires ``GITHUB_APP_ID``, ``GITHUB_APP_PRIVATE_KEY``,
  and ``GITHUB_APP_INSTALLATION_ID`` env vars.

Both share the same :class:`GitHubClient` interface so calling code
never cares which auth strategy is in play.
"""
from __future__ import annotations

import abc
import os
import time
from typing import Any, Optional

import httpx

from app.aep.observability import aep_logger

_logger = aep_logger("aep.github.client")

GITHUB_API_BASE = "https://api.github.com"
_ACCEPT = "application/vnd.github+json"
_API_VERSION = "2022-11-28"


class GitHubClient(abc.ABC):
    """Interface every GitHub auth strategy must implement."""

    @abc.abstractmethod
    async def _auth_headers(self) -> dict[str, str]:
        """Return auth headers for the current request."""

    # ── low-level helpers ────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        headers = await self._auth_headers()
        headers.update({
            "Accept": _ACCEPT,
            "X-GitHub-Api-Version": _API_VERSION,
        })
        url = f"{GITHUB_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, url, headers=headers, json=json_body, params=params,
            )
            if resp.status_code == 404:
                raise GitHubNotFoundError(f"GitHub 404: {path}")
            if resp.status_code == 422:
                raise GitHubValidationError(resp.json())
            resp.raise_for_status()
            if resp.status_code == 204:
                return {}
            return resp.json()

    async def _request_list(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        max_pages: int = 5,
    ) -> list[dict[str, Any]]:
        """Paginated GET returning a flat list."""
        results: list[dict[str, Any]] = []
        _params = dict(params or {})
        _params.setdefault("per_page", 100)
        page = 1
        while page <= max_pages:
            _params["page"] = page
            data = await self._request("GET", path, params=_params)
            if isinstance(data, list):
                if not data:
                    break
                results.extend(data)
                page += 1
            else:
                results.append(data)
                break
        return results

    # ── high-level API surface ───────────────────────────────────────

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def list_branches(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self._request_list(f"/repos/{owner}/{repo}/branches")

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict[str, Any]:
        return await self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")

    async def list_files(
        self, owner: str, repo: str, path: str = "", *, ref: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        data = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
        return data if isinstance(data, list) else [data]

    async def read_file(
        self, owner: str, repo: str, path: str, *, ref: Optional[str] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        return await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)

    async def create_branch(
        self, owner: str, repo: str, branch: str, sha: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json_body={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    async def write_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content_b64: str,
        message: str,
        branch: str,
        *,
        sha: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "message": message,
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        return await self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json_body=body)

    async def open_pull_request(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json_body={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft,
            },
        )

    async def list_workflow_runs(
        self, owner: str, repo: str, *, status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/runs", params=params)
        return data.get("workflow_runs", []) if isinstance(data, dict) else data

    async def get_workflow_run(
        self, owner: str, repo: str, run_id: int,
    ) -> dict[str, Any]:
        return await self._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    async def dispatch_workflow(
        self, owner: str, repo: str, workflow_id: str, ref: str,
        *, inputs: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"ref": ref}
        if inputs:
            body["inputs"] = inputs
        return await self._request(
            "POST",
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json_body=body,
        )

    async def get_rate_limit(self) -> dict[str, Any]:
        return await self._request("GET", "/rate_limit")


# ─────────────────────────────────────────────────────────────────────────────
# PAT implementation
# ─────────────────────────────────────────────────────────────────────────────


class PersonalAccessTokenClient(GitHubClient):
    """GitHub client using a personal access token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"token {self._token}"}


# ─────────────────────────────────────────────────────────────────────────────
# GitHub App implementation
# ─────────────────────────────────────────────────────────────────────────────


class GitHubAppClient(GitHubClient):
    """GitHub client using GitHub App installation tokens.

    Generates short-lived installation tokens (1 hr) via JWT auth and
    caches them with a 50-min TTL.
    """

    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        installation_id: str,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self._token: Optional[str] = None
        self._token_expires: float = 0.0

    def _generate_jwt(self) -> str:
        import jwt as pyjwt

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),
            "iss": self._app_id,
        }
        return pyjwt.encode(payload, self._private_key, algorithm="RS256")

    async def _ensure_installation_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        jwt_token = self._generate_jwt()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GITHUB_API_BASE}/app/installations/{self._installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": _ACCEPT,
                    "X-GitHub-Api-Version": _API_VERSION,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["token"]
        self._token_expires = time.time() + 50 * 60
        _logger.info(
            "github_app_token_refreshed",
            installation_id=self._installation_id,
        )
        return self._token  # type: ignore[return-value]

    async def _auth_headers(self) -> dict[str, str]:
        token = await self._ensure_installation_token()
        return {"Authorization": f"token {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# OAuth implementation
# ─────────────────────────────────────────────────────────────────────────────


class OAuthClient(GitHubClient):
    """GitHub client using an OAuth access token.

    Used when acting on behalf of a logged-in user through the
    OAuth flow. The token comes from the application's OAuth callback
    and is stored per-session in the user record.
    """

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    async def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Error types
# ─────────────────────────────────────────────────────────────────────────────


class GitHubClientError(Exception):
    """Base error for all GitHub client errors."""


class GitHubNotFoundError(GitHubClientError):
    """GitHub returned 404."""


class GitHubValidationError(GitHubClientError):
    """GitHub returned 422."""

    def __init__(self, detail: Any) -> None:
        self.detail = detail
        super().__init__(str(detail))


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

_singleton: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Return the process-wide GitHub client singleton.

    Auth strategy is chosen from environment variables:
    * ``GITHUB_APP_ID`` + ``GITHUB_APP_PRIVATE_KEY`` +
      ``GITHUB_APP_INSTALLATION_ID`` → :class:`GitHubAppClient`
    * ``GITHUB_TOKEN`` (or ``GH_TOKEN``) → :class:`PersonalAccessTokenClient`
    """
    global _singleton
    if _singleton is not None:
        return _singleton

    app_id = os.environ.get("GITHUB_APP_ID", "")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID", "")

    if app_id and private_key and installation_id:
        _singleton = GitHubAppClient(
            app_id=app_id,
            private_key=private_key,
            installation_id=installation_id,
        )
        _logger.info("github_client_initialized", auth="github_app")
        return _singleton

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if token:
        _singleton = PersonalAccessTokenClient(token)
        _logger.info("github_client_initialized", auth="pat")
        return _singleton

    _logger.warning("github_client_no_credentials")
    raise RuntimeError(
        "No GitHub credentials found. Set GITHUB_TOKEN or "
        "GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY + GITHUB_APP_INSTALLATION_ID."
    )


def reset_github_client() -> None:
    """Reset the singleton — used by tests."""
    global _singleton
    _singleton = None
