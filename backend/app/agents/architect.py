"""Architect — generates architecture, repo structure, DB designs, API contracts."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class Architect(BaseAgent):
    name = "architect"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        specification = context.get("specification", "")
        plan = context.get("plan", "")
        tech_stack = context.get("tech_stack", {})

        result = await self.llm(
            messages=[{"role": "user", "content": f"""Design the system architecture for this project.

Specification:
{specification}

Implementation plan:
{plan}

Tech stack constraints:
{tech_stack}

Output a JSON object with:
- "architecture_overview": high-level description
- "components": list of {{name, responsibility, tech, dependencies}}
- "repository_structure": nested dict representing directory tree
- "database_schema": list of {{table, columns: list of {{name, type, constraints}}, indexes}}
- "api_contracts": list of {{method, path, description, request_schema, response_schema}}
- "deployment_architecture": description of deploy targets and topology
- "security_considerations": list of strings
"""}],
            category=TaskCategory.SYSTEM_DESIGN,
            system="You are a principal software architect. Output valid JSON only.",
            max_tokens=8192,
        )

        return {"architecture": result.content, "tokens": result.input_tokens + result.output_tokens}
