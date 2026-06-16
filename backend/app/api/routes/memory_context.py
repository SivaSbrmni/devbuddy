"""Memory Context API - Fetch and manage memory for conversations.

Provides endpoints for:
- Fetching memory context for a conversation
- Manually updating memory
- Extracting insights from conversations
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.user import User
from app.services.memory_service import memory_service, PromptInjector
from app.services.memory_extractor import memory_extractor

router = APIRouter(prefix="/memory-context", tags=["memory"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class MemoryContextResponse(BaseModel):
    conversation_id: Optional[str]
    user_preferences: dict
    repository_memory: dict
    conversation_memory: dict
    previous_task: Optional[dict]


class UpdateGoalRequest(BaseModel):
    goal: str


class RecordDecisionRequest(BaseModel):
    decision: str
    context: Optional[dict] = None


class AddOpenTaskRequest(BaseModel):
    title: str
    description: str = ""


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/conversation/{conversation_id}")
async def get_conversation_memory(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> MemoryContextResponse:
    """Get full memory context for a conversation."""
    from app.models.conversation import Conversation
    from sqlalchemy import select
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        # Verify ownership
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Build memory context
        memory = await memory_service.build_memory_context(
            user_id=user.id,
            conversation_id=conversation_id,
            repo_url=conv.repository_url,
        )

        return MemoryContextResponse(
            conversation_id=str(conversation_id),
            user_preferences=memory.user_preferences,
            repository_memory={
                "architecture": memory.repo_architecture,
                "coding_standards": memory.coding_standards,
                "recent_changes": memory.recent_changes,
                "known_issues": memory.known_issues,
            },
            conversation_memory={
                "summary": memory.conversation_summary,
                "current_goal": memory.current_goal,
                "completed_tasks": memory.completed_tasks,
                "open_tasks": memory.open_tasks,
                "modified_files": memory.modified_files,
                "important_decisions": memory.important_decisions,
            },
            previous_task=memory.previous_task_context,
        )


@router.post("/conversation/{conversation_id}/goal")
async def update_conversation_goal(
    conversation_id: uuid.UUID,
    req: UpdateGoalRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Update the current goal for a conversation."""
    await memory_extractor.update_conversation_goal(conversation_id, req.goal)
    return {"success": True, "goal": req.goal}


@router.post("/conversation/{conversation_id}/decision")
async def record_decision(
    conversation_id: uuid.UUID,
    req: RecordDecisionRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Record an important architectural decision."""
    await memory_extractor.extract_important_decision(
        conversation_id, req.decision, req.context
    )
    return {"success": True, "decision": req.decision}


@router.post("/conversation/{conversation_id}/open-task")
async def add_open_task(
    conversation_id: uuid.UUID,
    req: AddOpenTaskRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Add a task to the open tasks list."""
    await memory_extractor.add_open_task(
        conversation_id, req.title, req.description
    )
    return {"success": True, "title": req.title}


@router.get("/user/preferences")
async def get_user_preferences(
    user: User = Depends(get_current_user),
) -> dict:
    """Get current user preferences."""
    from app.models.user_memory import UserMemory
    from sqlalchemy import select
    from app.db.session import async_session_factory

    async with async_session_factory() as db:
        stmt = select(UserMemory).where(UserMemory.user_id == user.id)
        result = await db.execute(stmt)
        mem = result.scalar_one_or_none()

        if not mem:
            return {}

        return {
            "preferred_language": mem.preferred_language,
            "preferred_framework": mem.preferred_framework,
            "coding_style": mem.coding_style,
            "commit_style": mem.commit_style,
            "pr_style": mem.pr_style,
            "testing_preference": mem.testing_preference,
            "documentation_style": mem.documentation_style,
            "response_style": mem.response_style,
            "preferred_architecture": mem.preferred_architecture,
            "custom_instructions": mem.custom_instructions,
        }


@router.patch("/user/preferences")
async def update_user_preferences(
    updates: dict,
    user: User = Depends(get_current_user),
) -> dict:
    """Update user preferences."""
    await memory_extractor.update_user_preferences(user.id, updates)
    return {"success": True}


# ─── Internal Helper for LLM Router ──────────────────────────────────────────

async def build_prompt_with_memory(
    user_id: uuid.UUID,
    conversation_id: Optional[uuid.UUID],
    base_prompt: str,
    repo_url: Optional[str] = None,
) -> str:
    """Build a complete prompt with all memory context injected.

    Used by the LLM router to automatically include memory in every request.
    """
    memory = await memory_service.build_memory_context(
        user_id=user_id,
        conversation_id=conversation_id,
        repo_url=repo_url,
    )

    return PromptInjector.inject_memory(base_prompt, memory)
