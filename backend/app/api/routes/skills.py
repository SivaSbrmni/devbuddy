"""Skill system API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.project import SkillOut
from app.skills.manager import SkillManager

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=list[SkillOut])
async def list_skills(
    category: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[SkillOut]:
    mgr = SkillManager(db)
    skills = await mgr.list_skills(category)
    return [SkillOut.model_validate(s) for s in skills]


@router.post("/seed")
async def seed_skills(db: AsyncSession = Depends(get_db)) -> dict:
    mgr = SkillManager(db)
    count = await mgr.seed_builtins()
    return {"seeded": count}
