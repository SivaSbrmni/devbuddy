"""Skill Manager — reusable engineering skills (templated procedures).

Each skill contains metadata, steps, examples, validation rules, success criteria.
Successful skills become reusable assets.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Skill

log = structlog.get_logger()


# Built-in skill templates
BUILTIN_SKILLS: list[dict[str, Any]] = [
    {
        "name": "create_fastapi_service",
        "description": "Scaffold a FastAPI microservice with standard structure",
        "category": "backend",
        "steps": [
            {"order": 1, "action": "create_directory", "args": {"structure": "app/{main,models,routes,schemas}.py"}},
            {"order": 2, "action": "write_file", "args": {"path": "requirements.txt"}},
            {"order": 3, "action": "write_file", "args": {"path": "app/main.py", "template": "fastapi_main"}},
            {"order": 4, "action": "write_file", "args": {"path": "Dockerfile", "template": "python_dockerfile"}},
            {"order": 5, "action": "exec", "args": {"command": "pip install -r requirements.txt"}},
            {"order": 6, "action": "exec", "args": {"command": "python -c 'from app.main import app'"}},
        ],
        "validation_rules": [{"check": "import_succeeds", "module": "app.main"}],
        "success_criteria": [{"criterion": "server_starts", "url": "http://localhost:8000/docs"}],
    },
    {
        "name": "create_react_app",
        "description": "Scaffold a React + Vite frontend",
        "category": "frontend",
        "steps": [
            {"order": 1, "action": "exec", "args": {"command": "npm create vite@latest . -- --template react-ts"}},
            {"order": 2, "action": "exec", "args": {"command": "npm install"}},
            {"order": 3, "action": "exec", "args": {"command": "npm run build"}},
        ],
        "validation_rules": [{"check": "build_succeeds"}],
        "success_criteria": [{"criterion": "dist_exists"}],
    },
    {
        "name": "deploy_railway",
        "description": "Deploy a project to Railway",
        "category": "deployment",
        "steps": [
            {"order": 1, "action": "validate", "args": {"check": "railway_token_exists"}},
            {"order": 2, "action": "exec", "args": {"command": "railway up --detach"}},
            {"order": 3, "action": "validate", "args": {"check": "health_check"}},
        ],
        "validation_rules": [{"check": "deploy_healthy"}],
        "success_criteria": [{"criterion": "http_200"}],
    },
    {
        "name": "deploy_vercel",
        "description": "Deploy a frontend to Vercel",
        "category": "deployment",
        "steps": [
            {"order": 1, "action": "exec", "args": {"command": "npx vercel --prod --yes"}},
            {"order": 2, "action": "validate", "args": {"check": "health_check"}},
        ],
        "validation_rules": [{"check": "deploy_healthy"}],
        "success_criteria": [{"criterion": "http_200"}],
    },
    {
        "name": "fix_python_exception",
        "description": "Debug and fix a Python exception",
        "category": "debugging",
        "steps": [
            {"order": 1, "action": "collect_evidence", "args": {"type": "stack_trace"}},
            {"order": 2, "action": "read_source", "args": {"from": "stack_trace"}},
            {"order": 3, "action": "form_hypothesis"},
            {"order": 4, "action": "generate_fix"},
            {"order": 5, "action": "apply_fix"},
            {"order": 6, "action": "run_tests"},
            {"order": 7, "action": "verify_resolution"},
        ],
        "validation_rules": [{"check": "tests_pass"}],
        "success_criteria": [{"criterion": "no_exception"}],
    },
    {
        "name": "create_ci_pipeline",
        "description": "Create a GitHub Actions CI pipeline",
        "category": "devops",
        "steps": [
            {"order": 1, "action": "create_directory", "args": {"path": ".github/workflows"}},
            {"order": 2, "action": "write_file", "args": {"path": ".github/workflows/ci.yml", "template": "ci_yaml"}},
            {"order": 3, "action": "commit_push"},
            {"order": 4, "action": "validate", "args": {"check": "workflow_runs"}},
        ],
        "validation_rules": [{"check": "workflow_valid"}],
        "success_criteria": [{"criterion": "ci_green"}],
    },
]


class SkillManager:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def seed_builtins(self) -> int:
        """Insert built-in skills if they don't exist."""
        count = 0
        for skill_data in BUILTIN_SKILLS:
            stmt = select(Skill).where(Skill.name == skill_data["name"])
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none() is None:
                skill = Skill(
                    name=skill_data["name"],
                    description=skill_data["description"],
                    category=skill_data["category"],
                    steps=skill_data["steps"],
                    validation_rules=skill_data.get("validation_rules", []),
                    success_criteria=skill_data.get("success_criteria", []),
                )
                self.db.add(skill)
                count += 1
        if count:
            await self.db.flush()
            log.info("skills.seeded", count=count)
        return count

    async def get_skill(self, name: str) -> Skill | None:
        stmt = select(Skill).where(Skill.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_skills(self, category: str | None = None) -> list[Skill]:
        stmt = select(Skill)
        if category:
            stmt = stmt.where(Skill.category == category)
        stmt = stmt.order_by(Skill.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_skill(self, data: dict[str, Any]) -> Skill:
        skill = Skill(**data)
        self.db.add(skill)
        await self.db.flush()
        log.info("skills.created", name=data.get("name"))
        return skill

    async def record_usage(self, name: str, success: bool) -> None:
        skill = await self.get_skill(name)
        if skill:
            skill.usage_count += 1
            if skill.success_rate is None:
                skill.success_rate = 1.0 if success else 0.0
            else:
                # Rolling average
                skill.success_rate = skill.success_rate * 0.9 + (1.0 if success else 0.0) * 0.1
            await self.db.flush()
