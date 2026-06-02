"""Engineering Workspace Manager — the virtual developer laptop.

Provides file ops, shell ops, runtime ops, log ops.
Each project gets an isolated workspace directory.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import structlog
from datetime import timezone as _tz

from app.core.config import settings

_UTC = _tz.utc

log = structlog.get_logger()


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now(tz=_UTC).isoformat())


@dataclass
class WorkspaceInfo:
    workspace_id: str
    project_id: str
    root_path: Path
    repo_path: Path | None
    created_at: str


class WorkspaceManager:
    """Manages isolated workspaces for each project."""

    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceInfo] = {}
        self._execution_history: dict[str, list[CommandResult]] = {}

    async def create_workspace(self, project_id: str) -> WorkspaceInfo:
        workspace_id = str(uuid.uuid4())[:8]
        root = settings.WORKSPACE_ROOT / f"ws-{workspace_id}"
        root.mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir(exist_ok=True)
        (root / "logs").mkdir(exist_ok=True)
        (root / "artifacts").mkdir(exist_ok=True)

        info = WorkspaceInfo(
            workspace_id=workspace_id,
            project_id=project_id,
            root_path=root,
            repo_path=None,
            created_at=datetime.now(tz=_UTC).isoformat(),
        )
        self._workspaces[workspace_id] = info
        self._execution_history[workspace_id] = []
        log.info("workspace.created", workspace_id=workspace_id, path=str(root))
        return info

    async def destroy_workspace(self, workspace_id: str) -> None:
        info = self._workspaces.pop(workspace_id, None)
        if info and info.root_path.exists():
            shutil.rmtree(info.root_path, ignore_errors=True)
        self._execution_history.pop(workspace_id, None)
        log.info("workspace.destroyed", workspace_id=workspace_id)

    # ── File Operations ─────────────────────────────────────────────
    async def read_file(self, workspace_id: str, path: str) -> str:
        full = self._resolve(workspace_id, path)
        async with aiofiles.open(full, "r") as f:
            return await f.read()

    async def write_file(self, workspace_id: str, path: str, content: str) -> None:
        full = self._resolve(workspace_id, path)
        full.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full, "w") as f:
            await f.write(content)
        log.debug("workspace.file_written", workspace_id=workspace_id, path=path)

    async def edit_file(
        self, workspace_id: str, path: str, old: str, new: str
    ) -> bool:
        content = await self.read_file(workspace_id, path)
        if old not in content:
            return False
        await self.write_file(workspace_id, path, content.replace(old, new, 1))
        return True

    async def delete_file(self, workspace_id: str, path: str) -> None:
        full = self._resolve(workspace_id, path)
        if full.exists():
            full.unlink()

    async def list_files(self, workspace_id: str, path: str = ".") -> list[str]:
        full = self._resolve(workspace_id, path)
        if not full.is_dir():
            return []
        result = []
        for item in sorted(full.rglob("*")):
            if item.is_file():
                result.append(str(item.relative_to(self._workspaces[workspace_id].root_path)))
        return result

    # ── Shell Operations ────────────────────────────────────────────
    async def exec_command(
        self, workspace_id: str, command: str, *, timeout: int = 120, cwd: str | None = None
    ) -> CommandResult:
        info = self._workspaces[workspace_id]
        work_dir = Path(cwd) if cwd else info.root_path

        import time
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
                env={**os.environ, "WORKSPACE_ID": workspace_id},
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            duration = int((time.monotonic() - start) * 1000)
            result = CommandResult(
                command=command,
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode(errors="replace")[-10000:],  # cap output
                stderr=stderr_bytes.decode(errors="replace")[-10000:],
                duration_ms=duration,
            )
        except asyncio.TimeoutError:
            duration = int((time.monotonic() - start) * 1000)
            result = CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                duration_ms=duration,
            )

        self._execution_history[workspace_id].append(result)
        log.info(
            "workspace.exec",
            workspace_id=workspace_id,
            command=command[:100],
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
        )
        return result

    # ── Log Operations ──────────────────────────────────────────────
    async def read_logs(self, workspace_id: str, log_file: str) -> str:
        logs_dir = self._workspaces[workspace_id].root_path / "logs"
        full = logs_dir / log_file
        if not full.exists():
            return ""
        async with aiofiles.open(full, "r") as f:
            return await f.read()

    async def search_logs(self, workspace_id: str, pattern: str) -> list[dict[str, Any]]:
        result = await self.exec_command(
            workspace_id,
            f'grep -rn "{pattern}" logs/ 2>/dev/null || true',
        )
        matches = []
        for line in result.stdout.strip().split("\n"):
            if ":" in line and line.strip():
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append({"file": parts[0], "line": parts[1], "content": parts[2]})
        return matches

    def get_execution_history(self, workspace_id: str) -> list[CommandResult]:
        return self._execution_history.get(workspace_id, [])

    # ── Git Operations ──────────────────────────────────────────────
    async def clone_repo(self, workspace_id: str, repo_url: str, branch: str = "main") -> CommandResult:
        info = self._workspaces[workspace_id]
        repo_dir = info.root_path / "repo"
        result = await self.exec_command(
            workspace_id,
            f"git clone --branch {branch} --depth 1 {repo_url} {repo_dir}",
        )
        if result.exit_code == 0:
            info.repo_path = repo_dir
        return result

    async def commit_and_push(
        self, workspace_id: str, message: str, branch: str | None = None
    ) -> CommandResult:
        info = self._workspaces[workspace_id]
        repo = info.repo_path or info.root_path / "repo"
        cmds = [
            "git add -A",
            f'git commit -m "{message}"',
        ]
        if branch:
            cmds.append(f"git push origin {branch}")
        else:
            cmds.append("git push")
        return await self.exec_command(workspace_id, " && ".join(cmds), cwd=str(repo))

    # ── Helpers ──────────────────────────────────────────────────────
    def _resolve(self, workspace_id: str, path: str) -> Path:
        info = self._workspaces[workspace_id]
        resolved = (info.root_path / path).resolve()
        # Security: prevent path traversal
        if not str(resolved).startswith(str(info.root_path)):
            raise PermissionError(f"Path traversal blocked: {path}")
        return resolved


# Singleton
workspace_manager = WorkspaceManager()
