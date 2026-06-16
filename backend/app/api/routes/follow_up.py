"""Follow-up API - Detect and handle follow-up messages.

Endpoints for analyzing if a message is a follow-up and creating
linked tasks with proper context inheritance.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.user import User
from app.services.follow_up_service import follow_up_service, FollowUpAnalysis

router = APIRouter(prefix="/follow-up", tags=["follow-up"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    conversation_id: str
    message: str


class AnalyzeResponse(BaseModel):
    is_follow_up: bool
    confidence: float
    previous_task_id: Optional[str]
    suggested_action: str  # 'continue', 'new_branch', 'new_task'
    previous_branch: Optional[str]
    inherited_files: list[str]


class CreateTaskRequest(BaseModel):
    conversation_id: str
    message: str
    force_new_task: bool = False  # Override detection


class CreateTaskResponse(BaseModel):
    task_id: str
    is_follow_up: bool
    parent_task_id: Optional[str]
    branch: str
    previous_branch: Optional[str]
    inherited_files: list[str]
    confidence: float
    suggested_prompt_context: str


class TaskChainResponse(BaseModel):
    chain: list[dict]


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_message(
    req: AnalyzeRequest,
    user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    """Analyze if a message is a follow-up without creating a task."""
    from app.models.conversation import Conversation
    from sqlalchemy import select
    from app.db.session import async_session_factory
    
    # Verify ownership
    async with async_session_factory() as db:
        conv_stmt = select(Conversation).where(
            Conversation.id == uuid.UUID(req.conversation_id),
            Conversation.user_id == user.id,
        )
        conv_result = await db.execute(conv_stmt)
        conv = conv_result.scalar_one_or_none()
        
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Analyze the message
    analysis = await follow_up_service.handle_new_message(
        conversation_id=uuid.UUID(req.conversation_id),
        message=req.message,
    )
    
    return AnalyzeResponse(
        is_follow_up=analysis.get('is_follow_up', False),
        confidence=analysis.get('confidence', 0.5),
        previous_task_id=analysis.get('parent_task_id'),
        suggested_action='continue' if analysis.get('is_follow_up') else 'new_task',
        previous_branch=analysis.get('previous_branch'),
        inherited_files=analysis.get('inherited_files', []),
    )


@router.post("/create-task", response_model=CreateTaskResponse)
async def create_task_with_context(
    req: CreateTaskRequest,
    user: User = Depends(get_current_user),
) -> CreateTaskResponse:
    """Create a task with automatic follow-up detection."""
    from app.models.conversation import Conversation
    from sqlalchemy import select
    from app.db.session import async_session_factory
    
    # Verify ownership
    async with async_session_factory() as db:
        conv_stmt = select(Conversation).where(
            Conversation.id == uuid.UUID(req.conversation_id),
            Conversation.user_id == user.id,
        )
        conv_result = await db.execute(conv_stmt)
        conv = conv_result.scalar_one_or_none()
        
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Import semantic branch naming
    from app.services.semantic_branch import generate_semantic_branch_name
    
    # If forced new task, skip detection
    if req.force_new_task:
        # Create new task without follow-up logic
        from app.models.conversation import ConversationTask
        
        branch = generate_semantic_branch_name(req.message)
        
        async with async_session_factory() as db:
            task = ConversationTask(
                conversation_id=uuid.UUID(req.conversation_id),
                title=req.message[:100],
                description=req.message,
                branch=branch,
                status='pending',
            )
            db.add(task)
            await db.flush()
            
            # Update conversation open_tasks
            if not conv.open_tasks:
                conv.open_tasks = []
            conv.open_tasks.append({
                'task_id': str(task.id),
                'title': req.message[:100],
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
            })
            
            await db.commit()
            
            return CreateTaskResponse(
                task_id=str(task.id),
                is_follow_up=False,
                parent_task_id=None,
                branch=branch,
                previous_branch=None,
                inherited_files=[],
                confidence=1.0,
                suggested_prompt_context="",
            )
    
    # Use follow-up service to detect and create
    result = await follow_up_service.handle_new_message(
        conversation_id=uuid.UUID(req.conversation_id),
        message=req.message,
    )
    
    # Build suggested prompt context
    prompt_context = ""
    if result.get('is_follow_up') and result.get('parent_task_id'):
        prompt_context = f"""This is a follow-up to the previous task ({result.get('previous_branch')}).

Previous work context:
- Branch: {result.get('previous_branch')}
- Modified files: {', '.join(result.get('inherited_files', [])[:5])}

Continue working on the same codebase, building upon the previous changes."""
    
    return CreateTaskResponse(
        task_id=result['task_id'],
        is_follow_up=result['is_follow_up'],
        parent_task_id=result.get('parent_task_id'),
        branch=result['branch'],
        previous_branch=result.get('previous_branch'),
        inherited_files=result.get('inherited_files', []),
        confidence=result['confidence'],
        suggested_prompt_context=prompt_context,
    )


@router.get("/task-chain/{task_id}", response_model=TaskChainResponse)
async def get_task_chain(
    task_id: str,
    user: User = Depends(get_current_user),
) -> TaskChainResponse:
    """Get the full chain of related tasks (parent -> children)."""
    chain = await follow_up_service.get_task_chain(uuid.UUID(task_id))
    return TaskChainResponse(chain=chain)


@router.post("/continue-on-branch")
async def continue_on_branch(
    req: CreateTaskRequest,
    user: User = Depends(get_current_user),
) -> CreateTaskResponse:
    """Explicitly continue on the same branch as previous task."""
    from app.models.conversation import Conversation, ConversationTask
    from sqlalchemy import select
    from app.db.session import async_session_factory
    from datetime import datetime
    import re
    
    # Verify ownership
    async with async_session_factory() as db:
        conv_stmt = select(Conversation).where(
            Conversation.id == uuid.UUID(req.conversation_id),
            Conversation.user_id == user.id,
        )
        conv_result = await db.execute(conv_stmt)
        conv = conv_result.scalar_one_or_none()
        
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get most recent task
        recent_stmt = (
            select(ConversationTask)
            .where(ConversationTask.conversation_id == uuid.UUID(req.conversation_id))
            .order_by(ConversationTask.created_at.desc())
            .limit(1)
        )
        recent_result = await db.execute(recent_stmt)
        prev_task = recent_result.scalar_one_or_none()
        
        if not prev_task:
            # No previous task, create new with semantic branch name
            branch = generate_semantic_branch_name(req.message)
            task = ConversationTask(
                conversation_id=uuid.UUID(req.conversation_id),
                title=req.message[:100],
                description=req.message,
                branch=branch,
                status='pending',
            )
            db.add(task)
            await db.flush()
            
            if not conv.open_tasks:
                conv.open_tasks = []
            conv.open_tasks.append({
                'task_id': str(task.id),
                'title': req.message[:100],
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
            })
            
            await db.commit()
            
            return CreateTaskResponse(
                task_id=str(task.id),
                is_follow_up=False,
                parent_task_id=None,
                branch=branch,
                previous_branch=None,
                inherited_files=[],
                confidence=1.0,
                suggested_prompt_context="",
            )
        
        # Continue on same branch
        task = ConversationTask(
            conversation_id=uuid.UUID(req.conversation_id),
            parent_id=prev_task.id,
            previous_task_id=prev_task.id,
            title=req.message[:100],
            description=req.message,
            branch=prev_task.branch,  # Same branch!
            status='pending',
        )
        
        db.add(task)
        await db.flush()
        
        if not conv.open_tasks:
            conv.open_tasks = []
        conv.open_tasks.append({
            'task_id': str(task.id),
            'title': req.message[:100],
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
        })
        
        await db.commit()
        
        prompt_context = f"""Continue working on branch '{prev_task.branch}'.

Previous work:
- Files modified: {', '.join(prev_task.modified_files or [])}
- Commit: {prev_task.commit_hash or 'N/A'}

Build upon these changes."""
        
        return CreateTaskResponse(
            task_id=str(task.id),
            is_follow_up=True,
            parent_task_id=str(prev_task.id),
            branch=prev_task.branch,
            previous_branch=prev_task.branch,
            inherited_files=prev_task.modified_files or [],
            confidence=1.0,
            suggested_prompt_context=prompt_context,
        )


