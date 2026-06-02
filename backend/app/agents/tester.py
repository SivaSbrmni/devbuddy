"""Tester — generates unit, integration, and e2e tests."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.core.model_router import TaskCategory


class Tester(BaseAgent):
    name = "tester"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        code = context.get("code", "")
        specification = context.get("specification", "")
        test_type = context.get("test_type", "unit")  # unit | integration | e2e
        existing_tests = context.get("existing_tests", "")

        result = await self.llm(
            messages=[{"role": "user", "content": f"""Generate {test_type} tests for the following code.

Code under test:
{code}

Specification / requirements:
{specification}

Existing tests:
{existing_tests}

Requirements:
1. Cover happy paths and edge cases
2. Test error conditions
3. Use descriptive test names
4. Include assertions with clear messages
5. Follow existing test patterns if any

Output a JSON object with:
- "test_files": list of {{path, content}}
- "coverage_notes": description of what is covered
- "uncoverable": list of things that cannot be unit-tested (need integration/e2e)
"""}],
            category=TaskCategory.TEST_GENERATION,
            system="You are a senior QA engineer. Write thorough, maintainable tests. Output valid JSON only.",
            max_tokens=8192,
        )

        return {"tests": result.content, "tokens": result.input_tokens + result.output_tokens}
