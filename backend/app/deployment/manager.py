"""Deployment Manager — provider-agnostic deployment abstraction.

Providers: Railway, Vercel, Docker VPS.
Future providers must be pluggable.
Deployment logic remains provider-independent.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import DeploymentHistory
from app.workspace.manager import WorkspaceManager

log = structlog.get_logger()


class DeploymentProvider(ABC):
    """Base class for deployment providers."""

    name: str = "base"

    @abstractmethod
    async def deploy(self, workspace_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Execute deployment, return result dict."""

    @abstractmethod
    async def get_status(self, deployment_id: str) -> dict[str, Any]:
        """Check deployment status."""

    @abstractmethod
    async def rollback(self, deployment_id: str) -> dict[str, Any]:
        """Roll back a deployment."""


class RailwayProvider(DeploymentProvider):
    name = "railway"

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    async def deploy(self, workspace_id: str, config: dict[str, Any]) -> dict[str, Any]:
        result = await self.workspace.exec_command(
            workspace_id,
            "railway up --detach",
            timeout=300,
        )
        return {
            "provider": "railway",
            "success": result.exit_code == 0,
            "output": result.stdout,
            "error": result.stderr if result.exit_code != 0 else None,
        }

    async def get_status(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "unknown", "provider": "railway"}

    async def rollback(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "rollback_not_implemented", "provider": "railway"}


class VercelProvider(DeploymentProvider):
    name = "vercel"

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    async def deploy(self, workspace_id: str, config: dict[str, Any]) -> dict[str, Any]:
        result = await self.workspace.exec_command(
            workspace_id,
            "npx vercel --prod --yes",
            timeout=300,
        )
        return {
            "provider": "vercel",
            "success": result.exit_code == 0,
            "output": result.stdout,
            "error": result.stderr if result.exit_code != 0 else None,
        }

    async def get_status(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "unknown", "provider": "vercel"}

    async def rollback(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "rollback_not_implemented", "provider": "vercel"}


class DockerProvider(DeploymentProvider):
    name = "docker"

    def __init__(self, workspace: WorkspaceManager) -> None:
        self.workspace = workspace

    async def deploy(self, workspace_id: str, config: dict[str, Any]) -> dict[str, Any]:
        image_name = config.get("image_name", "app")
        tag = config.get("tag", "latest")

        # Build
        build = await self.workspace.exec_command(
            workspace_id,
            f"docker build -t {image_name}:{tag} .",
            timeout=600,
        )
        if build.exit_code != 0:
            return {"provider": "docker", "success": False, "error": build.stderr}

        # Push if registry is configured
        if config.get("registry"):
            push = await self.workspace.exec_command(
                workspace_id,
                f"docker push {config['registry']}/{image_name}:{tag}",
                timeout=300,
            )
            if push.exit_code != 0:
                return {"provider": "docker", "success": False, "error": push.stderr}

        return {"provider": "docker", "success": True, "image": f"{image_name}:{tag}"}

    async def get_status(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "unknown", "provider": "docker"}

    async def rollback(self, deployment_id: str) -> dict[str, Any]:
        return {"status": "rollback_not_implemented", "provider": "docker"}


class DeploymentManager:
    """Orchestrates deployments across providers."""

    def __init__(self, db: AsyncSession, workspace: WorkspaceManager) -> None:
        self.db = db
        self.workspace = workspace
        self._providers: dict[str, DeploymentProvider] = {
            "railway": RailwayProvider(workspace),
            "vercel": VercelProvider(workspace),
            "docker": DockerProvider(workspace),
        }

    def register_provider(self, provider: DeploymentProvider) -> None:
        self._providers[provider.name] = provider

    async def deploy(
        self,
        project_id: uuid.UUID,
        provider_name: str,
        workspace_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown deploy provider: {provider_name}")

        log.info("deployment.starting", provider=provider_name, project_id=str(project_id))

        # Record deployment attempt
        history = DeploymentHistory(
            project_id=project_id,
            provider=provider_name,
            environment=config.get("environment", "production"),
            version=config.get("version", ""),
            status="deploying",
            config=config,
        )
        self.db.add(history)
        await self.db.flush()

        # Execute deployment
        result = await provider.deploy(workspace_id, config)

        # Update history
        history.status = "success" if result.get("success") else "failed"
        history.result = result
        history.deployed_at = datetime.utcnow() if result.get("success") else None
        await self.db.flush()

        log.info("deployment.completed", provider=provider_name, success=result.get("success"))
        return result

    async def get_deployment_history(
        self, project_id: uuid.UUID, limit: int = 10
    ) -> list[DeploymentHistory]:
        from sqlalchemy import select

        stmt = (
            select(DeploymentHistory)
            .where(DeploymentHistory.project_id == project_id)
            .order_by(DeploymentHistory.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
