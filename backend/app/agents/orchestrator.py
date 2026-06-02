"""Task Orchestrator — the central coordinator.

Drives the full autonomous pipeline:
Requirements → Analysis → Planning → Architecture → Engineering Review →
Coding → Workspace → Review → Testing → Fix → Git → Execution →
Failure Analysis → Repair → Retry → Deployment → Monitoring → Improvement
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.architect import Architect
from app.agents.coder import Coder
from app.agents.deployment_agent import DeploymentAgent
from app.agents.planner import Planner
from app.agents.requirement_analyzer import RequirementAnalyzer
from app.agents.reviewer import Reviewer
from app.agents.tester import Tester
from app.core.model_router import ModelRouter
from app.memory.manager import MemoryManager

log = structlog.get_logger()


class TaskOrchestrator:
    """Coordinates agents to execute the full software engineering pipeline."""

    def __init__(self, db: AsyncSession, router: ModelRouter) -> None:
        self.db = db
        self.router = router
        self.memory = MemoryManager(db)

        # Instantiate agents
        self.requirement_analyzer = RequirementAnalyzer(router, db)
        self.planner = Planner(router, db)
        self.architect = Architect(router, db)
        self.coder = Coder(router, db)
        self.reviewer = Reviewer(router, db)
        self.tester = Tester(router, db)
        self.deployment_agent = DeploymentAgent(router, db)

    async def run_pipeline(
        self,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        requirements: str,
        tech_stack: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the analysis → planning → architecture pipeline.

        Returns intermediate artifacts. Coding/testing/repair are driven
        separately per-task via the API.
        """
        results: dict[str, Any] = {}
        project_context = await self.memory.build_context_string(project_id)

        # Stage 1: Requirement Analysis
        log.info("orchestrator.stage", stage="requirement_analysis")
        analysis = await self.requirement_analyzer.run(
            task_id,
            {"requirements": requirements, "project_context": project_context},
        )
        results["specification"] = analysis.get("specification", "")
        await self.memory.store(
            project_id, "requirements", "Structured Specification", results["specification"]
        )

        # Stage 2: Planning
        log.info("orchestrator.stage", stage="planning")
        plan = await self.planner.run(
            task_id,
            {"specification": results["specification"], "project_memory": project_context},
        )
        results["plan"] = plan.get("plan", "")
        await self.memory.store(project_id, "milestones", "Implementation Plan", results["plan"])

        # Stage 3: Architecture
        log.info("orchestrator.stage", stage="architecture")
        architecture = await self.architect.run(
            task_id,
            {
                "specification": results["specification"],
                "plan": results["plan"],
                "tech_stack": tech_stack or {},
            },
        )
        results["architecture"] = architecture.get("architecture", "")
        await self.memory.store(
            project_id, "architecture", "System Architecture", results["architecture"]
        )

        return results

    async def run_coding_task(
        self,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        task_description: str,
        file_path: str = "",
        existing_code: str = "",
    ) -> dict[str, Any]:
        """Execute a coding task: code → review → test."""
        project_context = await self.memory.build_context_string(project_id)
        architecture = await self._get_memory_content(project_id, "architecture")

        # Stage 1: Generate code
        code_result = await self.coder.run(
            task_id,
            {
                "task_description": task_description,
                "architecture": architecture,
                "existing_code": existing_code,
                "coding_standards": await self._get_memory_content(project_id, "coding_standards"),
                "file_path": file_path,
            },
        )

        # Stage 2: Review (Engineering Review Gateway — Claude)
        review_result = await self.reviewer.run(
            task_id,
            {
                "code_changes": code_result.get("code_output", ""),
                "architecture": architecture,
                "review_type": "code",
            },
        )

        # Stage 3: Generate tests
        test_result = await self.tester.run(
            task_id,
            {
                "code": code_result.get("code_output", ""),
                "specification": project_context,
                "test_type": "unit",
            },
        )

        return {
            "code": code_result.get("code_output", ""),
            "review": review_result.get("review", ""),
            "tests": test_result.get("tests", ""),
        }

    async def _get_memory_content(self, project_id: uuid.UUID, category: str) -> str:
        memories = await self.memory.recall(project_id, category)
        return "\n\n".join(m.content for m in memories)
