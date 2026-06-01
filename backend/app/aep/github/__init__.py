"""AEP GitHub integration — Phase 2.

Provides an abstract GitHub client, webhook receiver, and repository
registration API so the AEP execution engine (Phase 3) can interact
with GitHub repositories programmatically.
"""

from app.aep.github.client import (
    GitHubClient,
    PersonalAccessTokenClient,
    GitHubAppClient,
    get_github_client,
)

__all__ = [
    "GitHubClient",
    "PersonalAccessTokenClient",
    "GitHubAppClient",
    "get_github_client",
]
