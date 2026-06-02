"""Deployment Agent — deploys applications, validates deployments."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class DeploymentAgent(BaseAgent):
    name = "deployment_agent"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        project_config = context.get("project_config", {})
        deploy_target = context.get("deploy_target", "railway")
        deployment_plan = context.get("deployment_plan", "")

        # Claude validates deployment plan (critical path)
        validation = await self.llm(
            messages=[{"role": "user", "content": f"""Review and validate this deployment plan.

Project config:
{project_config}

Deploy target: {deploy_target}

Deployment plan:
{deployment_plan}

Check for:
1. Missing environment variables
2. Missing build steps
3. Security issues
4. Health check configuration
5. Rollback strategy

Output a JSON object with:
- "approved": boolean
- "issues": list of {{severity, description, fix}}
- "deployment_commands": ordered list of shell commands
- "health_check": {{url, expected_status, timeout_s}}
- "rollback_plan": description
"""}],
            category=TaskCategory.DEPLOYMENT_VALIDATION,
            system="You are a senior SRE reviewing a deployment plan. Output valid JSON only.",
            max_tokens=4096,
        )

        return {
            "deployment_validation": validation.content,
            "tokens": validation.input_tokens + validation.output_tokens,
        }
