"""Coder — generates production code, tests, workflows, documentation."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class Coder(BaseAgent):
    name = "coder"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        task_description = context.get("task_description", "")
        architecture = context.get("architecture", "")
        existing_code = context.get("existing_code", "")
        coding_standards = context.get("coding_standards", "")
        file_path = context.get("file_path", "")

        result = await self.llm(
            messages=[{"role": "user", "content": f"""Generate production-quality code for the following task.

Task:
{task_description}

Architecture context:
{architecture}

Existing code (if modifying):
{existing_code}

Coding standards:
{coding_standards}

Target file path: {file_path}

Requirements:
1. Production-ready, not prototype quality
2. Proper error handling
3. Type annotations
4. Docstrings for public functions
5. Follow existing code conventions if modifying

Output a JSON object with:
- "files": list of {{path, content, action: "create"|"modify"|"delete"}}
- "explanation": brief description of changes
- "test_files": list of {{path, content}} for unit tests
"""}],
            category=TaskCategory.CODING,
            system="You are a principal software engineer. Write clean, production-ready code. Output valid JSON only.",
            max_tokens=8192,
        )

        return {"code_output": result.content, "tokens": result.input_tokens + result.output_tokens}
