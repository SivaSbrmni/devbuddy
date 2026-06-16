"""Memory Extractor - Automatically extract and store insights from conversations.

Updates conversation memory, repository memory, and user preferences based on:
- Task completions
- Code changes
- User feedback
- Important decisions
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

import structlog

from app.db.session import async_session_factory

log = structlog.get_logger()


class MemoryExtractor:
    """Extract knowledge from conversations and update memory."""

    def __init__(self):
        pass

    async def extract_from_task_completion(
        self,
        conversation_id: uuid.UUID,
        task_id: uuid.UUID,
        task_result: dict,
    ) -> None:
        """Extract memory when a task completes."""
        from app.models.conversation import Conversation, ConversationTask
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Get conversation and task
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await db.execute(conv_stmt)
            conv = conv_result.scalar_one_or_none()

            if not conv:
                return

            task_stmt = select(ConversationTask).where(ConversationTask.id == task_id)
            task_result_db = await db.execute(task_stmt)
            task = task_result_db.scalar_one_or_none()

            if not task:
                return

            # Update conversation memory
            await self._update_conversation_memory(db, conv, task, task_result)

            # Update repository memory if applicable
            if conv.repository_url:
                await self._update_repository_memory(db, conv, task, task_result)

            await db.commit()
            log.info("memory.extracted_from_task", conversation_id=str(conversation_id), task_id=str(task_id))

    async def _update_conversation_memory(
        self,
        db,
        conv,
        task,
        task_result: dict,
    ) -> None:
        """Update conversation working memory."""
        # Add completed task
        completed_task = {
            "task_id": str(task.id),
            "title": task.title,
            "summary": task_result.get("summary", ""),
            "branch": task.branch,
            "commit_hash": task.commit_hash,
            "pr_url": task.pr_url,
            "pr_number": task.pr_number,
            "modified_files": task.modified_files,
            "completed_at": datetime.utcnow().isoformat(),
        }

        if not conv.completed_tasks:
            conv.completed_tasks = []
        conv.completed_tasks.append(completed_task)

        # Update summary with LLM (or simple heuristic for now)
        if not conv.summary:
            conv.summary = f"Working on: {task.title}"
        else:
            # Simple append - in production use LLM to summarize
            conv.summary = f"{conv.summary}; Completed: {task.title}"

        # Clear current goal if task completed
        if conv.open_tasks:
            conv.open_tasks = [t for t in conv.open_tasks if t.get("task_id") != str(task.id)]

        # Add modified files
        if task.modified_files:
            if not conv.modified_files:
                conv.modified_files = []
            for f in task.modified_files:
                if f not in conv.modified_files:
                    conv.modified_files.append(f)

        # Extract important decisions from result
        if task_result.get("decisions"):
            if not conv.important_decisions:
                conv.important_decisions = []
            for d in task_result.get("decisions", []):
                conv.important_decisions.append({
                    "content": d,
                    "task_id": str(task.id),
                    "timestamp": datetime.utcnow().isoformat(),
                })

    async def _update_repository_memory(
        self,
        db,
        conv,
        task,
        task_result: dict,
    ) -> None:
        """Update repository knowledge based on changes."""
        from app.models.user_memory import RepositoryMemory
        from sqlalchemy import select

        # Get or create repo memory
        stmt = select(RepositoryMemory).where(RepositoryMemory.repo_url == conv.repository_url)
        result = await db.execute(stmt)
        repo_mem = result.scalar_one_or_none()

        if not repo_mem:
            # Create new repo memory
            repo_mem = RepositoryMemory(
                repo_url=conv.repository_url,
                repo_name=conv.repository_name or "",
                repo_owner=conv.repository_owner or "",
            )
            db.add(repo_mem)

        # Update recent changes
        if not repo_mem.recent_changes:
            repo_mem.recent_changes = []

        repo_mem.recent_changes.insert(0, {
            "task_id": str(task.id),
            "title": task.title,
            "files": task.modified_files,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep only last 20 changes
        repo_mem.recent_changes = repo_mem.recent_changes[:20]

        # Update tech stack from file changes (simple heuristic)
        if task.modified_files:
            langs = self._detect_languages(task.modified_files)
            if langs:
                if not repo_mem.tech_stack:
                    repo_mem.tech_stack = {}
                if "languages" not in repo_mem.tech_stack:
                    repo_mem.tech_stack["languages"] = []
                for lang in langs:
                    if lang not in repo_mem.tech_stack["languages"]:
                        repo_mem.tech_stack["languages"].append(lang)

        # Update conversation count
        repo_mem.conversation_count = (repo_mem.conversation_count or 0) + 1
        repo_mem.last_conversation_at = datetime.utcnow()

    def _detect_languages(self, files: List[str]) -> List[str]:
        """Detect programming languages from file extensions."""
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript/React",
            ".jsx": "JavaScript/React",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".kt": "Kotlin",
            ".rb": "Ruby",
            ".php": "PHP",
            ".cs": "C#",
            ".cpp": "C++",
            ".c": "C",
            ".swift": "Swift",
            ".scala": "Scala",
            ".r": "R",
            ".sh": "Shell",
            ".yml": "YAML",
            ".yaml": "YAML",
            ".json": "JSON",
            ".md": "Markdown",
            ".sql": "SQL",
        }

        detected = set()
        for f in files:
            for ext, lang in lang_map.items():
                if f.endswith(ext):
                    detected.add(lang)

        return list(detected)

    async def extract_important_decision(
        self,
        conversation_id: uuid.UUID,
        decision: str,
        context: Optional[dict] = None,
    ) -> None:
        """Manually record an important architectural decision."""
        from app.models.conversation import Conversation
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                return

            if not conv.important_decisions:
                conv.important_decisions = []

            conv.important_decisions.append({
                "content": decision,
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat(),
            })

            await db.commit()

    async def update_user_preferences(
        self,
        user_id: uuid.UUID,
        preferences: dict,
    ) -> None:
        """Update user memory with new preferences."""
        from app.models.user_memory import UserMemory
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = select(UserMemory).where(UserMemory.user_id == user_id)
            result = await db.execute(stmt)
            mem = result.scalar_one_or_none()

            if not mem:
                # Create new user memory
                mem = UserMemory(user_id=user_id)
                db.add(mem)

            # Update fields
            for field, value in preferences.items():
                if hasattr(mem, field):
                    setattr(mem, field, value)

            await db.commit()

    async def update_conversation_goal(
        self,
        conversation_id: uuid.UUID,
        goal: str,
    ) -> None:
        """Update the current goal for a conversation."""
        from app.models.conversation import Conversation
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()

            if conv:
                conv.current_goal = goal
                await db.commit()

    async def add_open_task(
        self,
        conversation_id: uuid.UUID,
        task_title: str,
        task_description: str = "",
    ) -> None:
        """Add a task to the open tasks list."""
        from app.models.conversation import Conversation
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                return

            if not conv.open_tasks:
                conv.open_tasks = []

            conv.open_tasks.append({
                "title": task_title,
                "description": task_description,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            })

            await db.commit()


# Singleton instance
memory_extractor = MemoryExtractor()
