"""Memory Service - 5-layer memory hierarchy retrieval and injection.

Fetches and injects memory from:
1. System Memory (global best practices)
2. Organization Memory (org standards)
3. User Memory (personal preferences)
4. Repository Memory (project knowledge)
5. Conversation Memory (current session context)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional
from dataclasses import dataclass

import structlog
from sqlalchemy import select

from app.db.session import async_session_factory

log = structlog.get_logger()


@dataclass
class MemoryContext:
    """Complete memory context for prompt injection."""
    
    # System
    system_prompt: str
    
    # Organization
    org_standards: str
    
    # User
    user_preferences: dict
    custom_instructions: str
    
    # Repository
    repo_architecture: str
    coding_standards: str
    recent_changes: list
    known_issues: list
    
    # Conversation
    conversation_summary: str
    current_goal: str
    completed_tasks: list
    open_tasks: list
    modified_files: list
    important_decisions: list
    
    # Previous task (for follow-ups)
    previous_task_context: Optional[dict] = None


class MemoryService:
    """Retrieve and format memory from all layers."""
    
    def __init__(self, db=None):
        self._db = db
    
    async def build_memory_context(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        repo_url: Optional[str] = None,
    ) -> MemoryContext:
        """Build complete memory context for a request."""
        
        # Fetch all layers in parallel
        user_mem, repo_mem, conv_mem, org_mem = await asyncio.gather(
            self._get_user_memory(user_id),
            self._get_repo_memory(repo_url) if repo_url else asyncio.coroutine(lambda: None)(),
            self._get_conversation_memory(conversation_id) if conversation_id else asyncio.coroutine(lambda: None)(),
            self._get_org_memory(user_id),
        )
        
        # Build previous task context if conversation exists
        previous_task = None
        if conv_mem and conv_mem.get("completed_tasks"):
            prev = conv_mem["completed_tasks"][-1]
            previous_task = {
                "branch": prev.get("branch"),
                "commit": prev.get("commit_hash"),
                "pr_url": prev.get("pr_url"),
                "files": prev.get("modified_files", []),
                "summary": prev.get("summary", ""),
            }
        
        return MemoryContext(
            system_prompt=await self._get_system_memory(),
            org_standards=org_mem.get("standards", ""),
            user_preferences=user_mem.get("preferences", {}),
            custom_instructions=user_mem.get("custom_instructions", ""),
            repo_architecture=repo_mem.get("architecture", "") if repo_mem else "",
            coding_standards=repo_mem.get("coding_standards", "") if repo_mem else "",
            recent_changes=repo_mem.get("recent_changes", []) if repo_mem else [],
            known_issues=repo_mem.get("known_issues", []) if repo_mem else [],
            conversation_summary=conv_mem.get("summary", "") if conv_mem else "",
            current_goal=conv_mem.get("current_goal", "") if conv_mem else "",
            completed_tasks=conv_mem.get("completed_tasks", []) if conv_mem else [],
            open_tasks=conv_mem.get("open_tasks", []) if conv_mem else [],
            modified_files=conv_mem.get("modified_files", []) if conv_mem else [],
            important_decisions=conv_mem.get("important_decisions", []) if conv_mem else [],
            previous_task_context=previous_task,
        )
    
    async def _get_user_memory(self, user_id: uuid.UUID) -> dict:
        """Fetch user preferences and custom instructions."""
        from app.models.user_memory import UserMemory
        
        async with async_session_factory() as db:
            stmt = select(UserMemory).where(UserMemory.user_id == user_id)
            result = await db.execute(stmt)
            mem = result.scalar_one_or_none()
            
            if not mem:
                return {}
            
            return {
                "preferences": {
                    "preferred_language": mem.preferred_language,
                    "preferred_framework": mem.preferred_framework,
                    "coding_style": mem.coding_style,
                    "commit_style": mem.commit_style,
                    "pr_style": mem.pr_style,
                    "testing_preference": mem.testing_preference,
                    "response_style": mem.response_style,
                },
                "custom_instructions": mem.custom_instructions,
            }
    
    async def _get_repo_memory(self, repo_url: str) -> Optional[dict]:
        """Fetch repository knowledge."""
        from app.models.user_memory import RepositoryMemory
        
        async with async_session_factory() as db:
            stmt = select(RepositoryMemory).where(RepositoryMemory.repo_url == repo_url)
            result = await db.execute(stmt)
            mem = result.scalar_one_or_none()
            
            if not mem:
                return None
            
            return {
                "architecture": mem.tech_stack,
                "coding_standards": mem.coding_standards,
                "recent_changes": mem.recent_changes[:5] if mem.recent_changes else [],
                "known_issues": mem.known_issues[:3] if mem.known_issues else [],
            }
    
    async def _get_conversation_memory(self, conversation_id: uuid.UUID) -> Optional[dict]:
        """Fetch conversation working memory."""
        from app.models.conversation import Conversation
        
        async with async_session_factory() as db:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            
            if not conv:
                return None
            
            return {
                "summary": conv.summary,
                "current_goal": conv.current_goal,
                "completed_tasks": conv.completed_tasks[-5:] if conv.completed_tasks else [],
                "open_tasks": conv.open_tasks,
                "modified_files": conv.modified_files,
                "important_decisions": conv.important_decisions[-3:] if conv.important_decisions else [],
            }
    
    async def _get_org_memory(self, user_id: uuid.UUID) -> dict:
        """Fetch organization standards."""
        from app.models.user import User
        from app.models.user_memory import OrganizationMemory
        
        async with async_session_factory() as db:
            # Get user's org
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {}
            
            # Get org standards
            org_stmt = select(OrganizationMemory).where(
                OrganizationMemory.org_id == user.org_id
            )
            org_result = await db.execute(org_stmt)
            standards = org_result.scalars().all()
            
            if not standards:
                return {}
            
            # Format as text
            standards_text = "\n\n".join([
                f"**{s.title}** ({s.category}):\n{s.content}"
                for s in standards[:5]
            ])
            
            return {"standards": standards_text}
    
    async def _get_system_memory(self) -> str:
        """Get global system prompt with best practices."""
        return """You are DevBuddy, an expert autonomous software engineering agent.

CORE PRINCIPLES:
- Write clean, maintainable code with proper error handling
- Follow the existing patterns in the codebase
- Add tests for new functionality
- Document complex logic with inline comments
- Use conventional commit messages
- Create detailed pull request descriptions

ENGINEERING STANDARDS:
- Prefer explicit over implicit
- Optimize for readability, then performance
- Handle edge cases gracefully
- Validate all inputs
- Never expose secrets or credentials in code"""


class PromptInjector:
    """Inject memory context into LLM prompts."""
    
    @staticmethod
    def inject_memory(prompt: str, memory: MemoryContext) -> str:
        """Build full prompt with memory context."""
        
        sections = [
            ("SYSTEM", memory.system_prompt),
            ("ORGANIZATION STANDARDS", memory.org_standards),
            ("USER PREFERENCES", PromptInjector._format_user_prefs(memory)),
            ("REPOSITORY KNOWLEDGE", PromptInjector._format_repo_memory(memory)),
            ("CONVERSATION CONTEXT", PromptInjector._format_conversation_memory(memory)),
            ("PREVIOUS TASK", PromptInjector._format_previous_task(memory.previous_task_context)),
            ("CURRENT REQUEST", prompt),
        ]
        
        # Only include non-empty sections
        included = []
        for title, content in sections:
            if content and content.strip():
                included.append(f"=== {title} ===\n{content}")
        
        return "\n\n".join(included)
    
    @staticmethod
    def _format_user_prefs(memory: MemoryContext) -> str:
        """Format user preferences as text."""
        prefs = memory.user_preferences
        if not prefs:
            return ""
        
        lines = []
        if prefs.get("preferred_language"):
            lines.append(f"Preferred language: {prefs['preferred_language']}")
        if prefs.get("coding_style"):
            lines.append(f"Coding style: {prefs['coding_style']}")
        if prefs.get("commit_style"):
            lines.append(f"Commit message style: {prefs['commit_style']}")
        if prefs.get("testing_preference"):
            lines.append(f"Testing: {prefs['testing_preference']}")
        
        if memory.custom_instructions:
            lines.append(f"\nCustom instructions:\n{memory.custom_instructions}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_repo_memory(memory: MemoryContext) -> str:
        """Format repository memory as text."""
        parts = []
        
        if memory.repo_architecture:
            parts.append(f"Architecture: {memory.repo_architecture}")
        
        if memory.coding_standards:
            parts.append(f"Standards:\n{memory.coding_standards}")
        
        if memory.known_issues:
            issues = "\n".join([f"- {i.get('title', '')}" for i in memory.known_issues[:3]])
            parts.append(f"Known issues:\n{issues}")
        
        return "\n\n".join(parts)
    
    @staticmethod
    def _format_conversation_memory(memory: MemoryContext) -> str:
        """Format conversation memory as text."""
        parts = []
        
        if memory.conversation_summary:
            parts.append(f"Summary: {memory.conversation_summary}")
        
        if memory.current_goal:
            parts.append(f"Current goal: {memory.current_goal}")
        
        if memory.completed_tasks:
            tasks = "\n".join([
                f"- {t.get('title', 'Unnamed task')}: {t.get('summary', 'No summary')[:100]}"
                for t in memory.completed_tasks[-3:]
            ])
            parts.append(f"Recently completed tasks:\n{tasks}")
        
        if memory.open_tasks:
            open_t = "\n".join([f"- {t.get('title', 'Task')}" for t in memory.open_tasks])
            parts.append(f"Open tasks:\n{open_t}")
        
        if memory.modified_files:
            files = ", ".join(memory.modified_files[-10:])
            parts.append(f"Files modified in this conversation: {files}")
        
        if memory.important_decisions:
            decisions = "\n".join([f"- {d.get('content', '')[:100]}" for d in memory.important_decisions])
            parts.append(f"Key decisions:\n{decisions}")
        
        return "\n\n".join(parts)
    
    @staticmethod
    def _format_previous_task(previous: Optional[dict]) -> str:
        """Format previous task context for follow-ups."""
        if not previous:
            return ""
        
        parts = []
        if previous.get("summary"):
            parts.append(f"Previous task summary: {previous['summary']}")
        if previous.get("branch"):
            parts.append(f"Branch: {previous['branch']}")
        if previous.get("commit"):
            parts.append(f"Commit: {previous['commit']}")
        if previous.get("files"):
            files = ", ".join(previous["files"][:5])
            parts.append(f"Files changed: {files}")
        
        return "\n".join(parts)


# Singleton instance
memory_service = MemoryService()
