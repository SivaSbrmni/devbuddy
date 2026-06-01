"""Repository registration API — Phase 2.

CRUD for ``aep_repositories``. Registering a repo makes it available to
the AEP execution engine for autonomous work.

Routes:
    POST   /api/v1/aep/repositories      — register a repo
    GET    /api/v1/aep/repositories      — list registered repos
    GET    /api/v1/aep/repositories/{id} — get one repo
    DELETE /api/v1/aep/repositories/{id} — unregister a repo
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aep.models import AepRepository
from app.aep.observability import aep_logger
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/aep/repositories", tags=["aep-repositories"])
_logger = aep_logger("aep.api.repositories")


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class RepoCreate(BaseModel):
    owner: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(default="github", max_length=50)
    default_branch: str = Field(default="main", max_length=255)
    auth_method: str = Field(default="pat", max_length=50)
    clone_url: Optional[str] = Field(
        default=None,
        description="HTTPS clone URL. Auto-generated as https://github.com/{owner}/{name}.git if omitted.",
    )
    installation_id: Optional[str] = Field(default=None, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)


class RepoOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    owner: str
    name: str
    provider: str
    default_branch: str
    auth_method: str
    clone_url: str
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class RepoListOut(BaseModel):
    repositories: list[RepoOut]
    count: int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _tenant_id(user: dict[str, Any]) -> uuid.UUID:
    payload = user.get("payload") or {}
    tid = payload.get("tenant_id") or payload.get("sub")
    return uuid.UUID(str(tid))


def _repo_to_out(repo: AepRepository) -> RepoOut:
    return RepoOut(
        id=repo.id,
        tenant_id=repo.tenant_id,
        owner=repo.owner,
        name=repo.name,
        provider=repo.provider,
        default_branch=repo.default_branch,
        auth_method=repo.auth_method,
        clone_url=repo.clone_url,
        is_active=repo.is_active,
        created_at=repo.created_at.isoformat() if repo.created_at else "",
        updated_at=repo.updated_at.isoformat() if repo.updated_at else "",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post("", response_model=RepoOut, status_code=status.HTTP_201_CREATED)
async def register_repository(
    body: RepoCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepoOut:
    """Register a repository for AEP autonomous work."""
    tenant = _tenant_id(user)

    existing = await db.execute(
        select(AepRepository).where(
            AepRepository.tenant_id == tenant,
            AepRepository.provider == body.provider,
            AepRepository.owner == body.owner,
            AepRepository.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository {body.owner}/{body.name} already registered",
        )

    clone_url = body.clone_url or f"https://github.com/{body.owner}/{body.name}.git"

    repo = AepRepository(
        tenant_id=tenant,
        owner=body.owner,
        name=body.name,
        provider=body.provider,
        default_branch=body.default_branch,
        auth_method=body.auth_method,
        clone_url=clone_url,
        installation_id=body.installation_id,
        config=body.config,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    _logger.info(
        "repository_registered",
        repo=f"{body.owner}/{body.name}",
        tenant=str(tenant),
    )
    return _repo_to_out(repo)


@router.get("", response_model=RepoListOut)
async def list_repositories(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepoListOut:
    """List all repositories registered for the current tenant."""
    tenant = _tenant_id(user)
    result = await db.execute(
        select(AepRepository)
        .where(AepRepository.tenant_id == tenant, AepRepository.is_active.is_(True))
        .order_by(AepRepository.created_at.desc())
    )
    repos = result.scalars().all()
    return RepoListOut(
        repositories=[_repo_to_out(r) for r in repos],
        count=len(repos),
    )


@router.get("/{repo_id}", response_model=RepoOut)
async def get_repository(
    repo_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepoOut:
    """Get a single registered repository."""
    tenant = _tenant_id(user)
    result = await db.execute(
        select(AepRepository).where(
            AepRepository.id == repo_id,
            AepRepository.tenant_id == tenant,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _repo_to_out(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_repository(
    repo_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a registered repository."""
    tenant = _tenant_id(user)
    result = await db.execute(
        select(AepRepository).where(
            AepRepository.id == repo_id,
            AepRepository.tenant_id == tenant,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo.is_active = False
    await db.commit()
    _logger.info(
        "repository_unregistered",
        repo=f"{repo.owner}/{repo.name}",
        tenant=str(tenant),
    )
