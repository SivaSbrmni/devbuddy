"""Tests for Priority 2 — GitHub Actions Dependency Caching."""

from __future__ import annotations

from app.execution.gha_runtime import (
    ExecutionPlan,
    GHARuntimeManager,
    PackageManager,
    detect_package_managers,
    build_cache_step,
)


class TestPackageManagerDetection:
    """Detect package managers by lockfile presence in repo root."""

    def test_detects_npm(self):
        managers = detect_package_managers({"file_tree": ["package-lock.json", "src/index.js"]})
        assert any(m.name == "npm" for m in managers)

    def test_detects_yarn_over_npm_when_both_present(self):
        managers = detect_package_managers({"file_tree": ["package-lock.json", "yarn.lock"]})
        names = [m.name for m in managers]
        # npm is first in config but yarn.lock also matches; both are detected
        assert "npm" in names
        assert "yarn" in names

    def test_detects_python_managers(self):
        managers = detect_package_managers({"file_tree": ["poetry.lock", "requirements.txt"]})
        names = [m.name for m in managers]
        assert "poetry" in names
        assert "pip" in names

    def test_detects_go_and_cargo(self):
        managers = detect_package_managers({"file_tree": ["go.sum", "Cargo.lock"]})
        names = [m.name for m in managers]
        assert "go" in names
        assert "cargo" in names

    def test_no_lockfile_no_manager(self):
        managers = detect_package_managers({"file_tree": ["README.md", "src/main.py"]})
        assert managers == []


class TestCacheStepYAML:
    """Generated cache step uses actions/cache@v4 with safe key."""

    def test_cache_step_contains_actions_cache_v4(self):
        manager = PackageManager("npm", "package-lock.json", ["node_modules", "~/.npm"])
        step = build_cache_step(manager)
        assert "uses: actions/cache@v4" in step
        assert "path:" in step
        assert "node_modules" in step
        assert "key: v1-npm-${{ runner.os }}-${{ hashFiles('package-lock.json') }}" in step

    def test_cache_step_restore_keys_do_not_include_user_input(self):
        manager = PackageManager("npm", "package-lock.json", ["node_modules"])
        step = build_cache_step(manager)
        assert "v1-npm-${{ runner.os }}-" in step
        assert "v1-npm-" in step
        # User-controllable strings should not appear in the key
        assert "bad-user-input" not in step


class TestWorkflowGeneration:
    """Generated workflow YAML contains cache steps in the right place."""

    def test_workflow_includes_cache_step_before_execute(self):
        manager = GHARuntimeManager()
        plan = ExecutionPlan(
            task_id="123",
            steps=[{"name": "test", "command": "pytest"}],
            estimated_cost={"repo": {"file_tree": ["package-lock.json", "src/index.js"]}},
        )
        yaml = manager.generate_workflow(plan)
        assert "actions/cache@v4" in yaml.content
        assert "Cache npm dependencies" in yaml.content
        assert "Execute Agent Steps" in yaml.content
        # Cache step should appear before execute
        cache_idx = yaml.content.index("Cache npm dependencies")
        execute_idx = yaml.content.index("Execute Agent Steps")
        assert cache_idx < execute_idx

    def test_monorepo_generates_multiple_cache_steps(self):
        manager = GHARuntimeManager()
        plan = ExecutionPlan(
            task_id="123",
            steps=[{"name": "build", "command": "npm run build"}],
            estimated_cost={"repo": {"file_tree": ["package-lock.json", "requirements.txt"]}},
        )
        yaml = manager.generate_workflow(plan)
        assert "Cache npm dependencies" in yaml.content
        assert "Cache pip dependencies" in yaml.content
