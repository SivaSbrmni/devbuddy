"""Consolidated GitHub client — spec Part 8.

Unifies all GitHub operations into a single client with support for
PAT, GitHub App, and OAuth authentication. Handles:
  - Repository cloning and branch management
  - Push changes and create pull requests
  - Workflow triggering and monitoring
  - Webhook signature verification and event parsing
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import httpx
import structlog

log = structlog.get_logger()


@dataclass
class GitHubAuth:
    """GitHub authentication configuration (spec Part 8)."""
    type: str  # 'pat', 'github_app', 'oauth'
    token: str = ""
    app_id: str = ""
    private_key: str = ""
    installation_id: str = ""
    access_token: str = ""

    @classmethod
    def pat(cls, token: str) -> "GitHubAuth":
        return cls(type="pat", token=token)

    @classmethod
    def github_app(cls, app_id: str, private_key: str, installation_id: str) -> "GitHubAuth":
        return cls(type="github_app", app_id=app_id, private_key=private_key, installation_id=installation_id)

    @classmethod
    def oauth(cls, access_token: str) -> "GitHubAuth":
        return cls(type="oauth", access_token=access_token)

    def get_auth_header(self) -> dict[str, str]:
        if self.type == "pat":
            return {"Authorization": f"token {self.token}"}
        elif self.type == "oauth":
            return {"Authorization": f"token {self.access_token}"}
        elif self.type == "github_app":
            # In production, this would generate a JWT and exchange for an installation token
            # For now, use the installation_id with a pre-generated token
            return {"Authorization": f"token {self.token}"}
        return {}


@dataclass
class Repository:
    owner: str
    repo: str
    default_branch: str = "main"
    installation_id: Optional[str] = None


@dataclass
class FileChange:
    path: str
    content: str
    action: str = "create"  # create, update, delete


@dataclass
class CommitResult:
    sha: str
    url: str
    message: str


@dataclass
class PRRequest:
    repo: Repository
    title: str
    body: str
    head: str  # branch name
    base: str = "main"


@dataclass
class PullRequest:
    number: int
    url: str
    state: str


@dataclass
class WorkflowRun:
    id: str
    status: str
    conclusion: Optional[str] = None
    html_url: str = ""


@dataclass
class WorkflowRunStatus:
    id: str
    status: str
    conclusion: Optional[str]
    jobs: list[dict] = field(default_factory=list)


@dataclass
class ArtifactBundle:
    artifacts: list[dict]


@dataclass
class GitHubEvent:
    event_type: str
    payload: dict
    delivery_id: str = ""


class GitHubClient:
    """Consolidated GitHub API client (spec Part 8).

    Handles all GitHub operations through a single authenticated client.
    Supports PAT, GitHub App, and OAuth authentication.
    """

    API_BASE = "https://api.github.com"

    def __init__(self, auth: GitHubAuth) -> None:
        self.auth = auth
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.API_BASE,
                headers={
                    **self.auth.get_auth_header(),
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── Repository Operations ────────────────────────────────────────────────

    async def clone_repository(self, repo: Repository, branch: str) -> str:
        """Clone a repository branch. Returns the local path.

        Note: Actual git clone is handled by the execution environment
        (GHA runner). This method returns the clone URL for reference.
        """
        token = self.auth.token or self.auth.access_token
        return f"https://{token}@github.com/{repo.owner}/{repo.repo}.git"

    async def create_branch(self, repo: Repository, name: str, from_branch: str = "main") -> dict:
        """Create a new branch from an existing branch."""
        client = await self._get_client()
        # Get the SHA of the source branch
        resp = await client.get(f"/repos/{repo.owner}/{repo.repo}/git/refs/heads/{from_branch}")
        resp.raise_for_status()
        sha = resp.json()["object"]["sha"]

        # Create the new branch
        resp = await client.post(
            f"/repos/{repo.owner}/{repo.repo}/git/refs",
            json={"ref": f"refs/heads/{name}", "sha": sha},
        )
        resp.raise_for_status()
        return resp.json()

    async def push_changes(self, repo: Repository, branch: str, files: list[FileChange]) -> CommitResult:
        """Push file changes to a branch via the GitHub API (no git needed)."""
        client = await self._get_client()

        # Get the current commit SHA
        resp = await client.get(f"/repos/{repo.owner}/{repo.repo}/git/refs/heads/{branch}")
        resp.raise_for_status()
        latest_commit_sha = resp.json()["object"]["sha"]

        # Get the current tree
        resp = await client.get(f"/repos/{repo.owner}/{repo.repo}/git/commits/{latest_commit_sha}")
        resp.raise_for_status()
        base_tree = resp.json()["tree"]["sha"]

        # Create blobs for each file
        tree_items = []
        for file_change in files:
            if file_change.action == "delete":
                tree_items.append({"path": file_change.path, "mode": "100644", "type": "blob", "sha": None})
            else:
                resp = await client.post(
                    f"/repos/{repo.owner}/{repo.repo}/git/blobs",
                    json={"content": file_change.content, "encoding": "utf-8"},
                )
                resp.raise_for_status()
                blob_sha = resp.json()["sha"]
                tree_items.append({"path": file_change.path, "mode": "100644", "type": "blob", "sha": blob_sha})

        # Create a new tree
        resp = await client.post(
            f"/repos/{repo.owner}/{repo.repo}/git/trees",
            json={"base_tree": base_tree, "tree": tree_items},
        )
        resp.raise_for_status()
        tree_sha = resp.json()["sha"]

        # Create a commit
        resp = await client.post(
            f"/repos/{repo.owner}/{repo.repo}/git/commits",
            json={"message": "DevBuddy autonomous changes", "tree": tree_sha, "parents": [latest_commit_sha]},
        )
        resp.raise_for_status()
        commit_sha = resp.json()["sha"]
        commit_url = resp.json()["html_url"]

        # Update the branch reference
        resp = await client.patch(
            f"/repos/{repo.owner}/{repo.repo}/git/refs/heads/{branch}",
            json={"sha": commit_sha},
        )
        resp.raise_for_status()

        return CommitResult(sha=commit_sha, url=commit_url, message="DevBuddy autonomous changes")

    async def create_pull_request(self, pr: PRRequest) -> PullRequest:
        """Create a pull request."""
        client = await self._get_client()
        resp = await client.post(
            f"/repos/{pr.repo.owner}/{pr.repo.repo}/pulls",
            json={"title": pr.title, "body": pr.body, "head": pr.head, "base": pr.base},
        )
        resp.raise_for_status()
        data = resp.json()
        return PullRequest(number=data["number"], url=data["html_url"], state=data["state"])

    async def add_pr_comment(self, repo: Repository, pr_number: int, body: str) -> None:
        """Add a comment to a pull request."""
        client = await self._get_client()
        resp = await client.post(
            f"/repos/{repo.owner}/{repo.repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        resp.raise_for_status()

    # ─── Workflow Operations ──────────────────────────────────────────────────

    async def trigger_workflow(self, repo: Repository, workflow_id: str, ref: str, inputs: dict[str, str]) -> WorkflowRun:
        """Trigger a workflow dispatch."""
        client = await self._get_client()
        resp = await client.post(
            f"/repos/{repo.owner}/{repo.repo}/actions/workflows/{workflow_id}/dispatches",
            json={"ref": ref, "inputs": inputs},
        )
        resp.raise_for_status()
        return WorkflowRun(id="pending", status="queued")

    async def get_workflow_run(self, repo: Repository, run_id: str) -> WorkflowRunStatus:
        """Get the status of a workflow run."""
        client = await self._get_client()
        resp = await client.get(f"/repos/{repo.owner}/{repo.repo}/actions/runs/{run_id}")
        resp.raise_for_status()
        data = resp.json()
        return WorkflowRunStatus(
            id=str(data["id"]),
            status=data["status"],
            conclusion=data.get("conclusion"),
        )

    async def stream_workflow_logs(self, repo: Repository, run_id: str) -> AsyncIterator[str]:
        """Stream workflow logs line by line."""
        client = await self._get_client()
        resp = await client.get(
            f"/repos/{repo.owner}/{repo.repo}/actions/runs/{run_id}/logs",
            follow_redirects=True,
        )
        if resp.status_code == 200:
            # Logs are returned as a zip file; for streaming, we yield raw bytes
            # In production, this would unzip and stream individual log files
            yield resp.text
        else:
            yield f"[Log fetch failed: {resp.status_code}]"

    async def cancel_workflow(self, repo: Repository, run_id: str) -> None:
        """Cancel a running workflow."""
        client = await self._get_client()
        resp = await client.post(f"/repos/{repo.owner}/{repo.repo}/actions/runs/{run_id}/cancel")
        resp.raise_for_status()

    async def download_artifacts(self, repo: Repository, run_id: str) -> ArtifactBundle:
        """Download artifacts from a completed workflow run."""
        client = await self._get_client()
        resp = await client.get(f"/repos/{repo.owner}/{repo.repo}/actions/runs/{run_id}/artifacts")
        resp.raise_for_status()
        return ArtifactBundle(artifacts=resp.json().get("artifacts", []))

    # ─── Webhook Verification ─────────────────────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify a GitHub webhook signature.

        GitHub sends X-Hub-Signature-256: sha256=<hex>
        """
        if not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        provided = signature[7:]  # Remove "sha256=" prefix
        return hmac.compare_digest(expected, provided)

    def parse_webhook_event(self, payload: bytes, event_type: str) -> GitHubEvent:
        """Parse a GitHub webhook event."""
        data = json.loads(payload)
        return GitHubEvent(
            event_type=event_type,
            payload=data,
            delivery_id="",  # Set from headers by the receiver
        )
