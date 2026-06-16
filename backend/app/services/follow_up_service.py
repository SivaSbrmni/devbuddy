"""Follow-up Service - Handle "Now add..." and task continuation.

Key features:
1. Detects if a message is a follow-up vs new task
2. Links tasks as parent/child for continuity
3. Continues on same branch or creates devbuddy/next-* branch
4. Inherits context from previous task automatically
"""

from __future__ import annotations

import uuid
import re
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import select

from app.db.session import async_session_factory
from app.services.semantic_branch import generate_semantic_branch_name

log = structlog.get_logger()


@dataclass
class FollowUpAnalysis:
    """Result of analyzing if a message is a follow-up."""
    is_follow_up: bool
    confidence: float  # 0-1
    previous_task_id: Optional[uuid.UUID]
    suggested_action: str  # 'continue', 'new_branch', 'new_task'
    context_inheritance: dict  # What to inherit from previous task


class FollowUpDetector:
    """Detect follow-up patterns in user messages."""
    
    # Patterns that indicate follow-up intent
    FOLLOW_UP_PATTERNS = [
        # Direct continuations
        r"^(?i)(now|then|next|also|additionally)\s+(add|implement|create|make|update|fix|change)",
        r"^(?i)(can you|please|now)\s+(also|additionally)?\s*(add|implement|create|make)",
        r"^(?i)(let'?s|we should|we need to)\s+(also|now)?\s*(add|implement|create)",
        
        # Referencing previous work
        r"(?i)(in\s+(that|the\s+same)|to\s+that|with\s+that)",
        r"(?i)(similarly|likewise|as\s+well|too)",
        r"(?i)(while\s+you['']?re\s+at\s+it|since\s+you['']?re\s+there)",
        
        # Implicit continuation
        r"^(?i)(and|but)\s+(also|now)?\s*(add|implement|create|make|update|fix)",
        r"(?i)(don['']?t\s+forget\s+to|remember\s+to)",
        
        # Specific file/location references
        r"(?i)(in\s+the\s+same\s+(file|component|module|class))",
        r"(?i)(update\s+the\s+same)",
    ]
    
    # Patterns that indicate NEW task (not follow-up)
    NEW_TASK_PATTERNS = [
        r"^(?i)(new|different|separate|another|unrelated)\s+(task|project|repo|feature)",
        r"^(?i)(let'?s\s+start\s+(over|fresh|new)|scratch\s+that)",
        r"^(?i)(forget\s+(about|the)\s+(previous|last)|ignore\s+that)",
        r"^(?i)(instead\s+of|rather\s+than|not\s+that)",
    ]
    
    @classmethod
    def analyze(
        cls,
        message: str,
        conversation_id: uuid.UUID,
    ) -> FollowUpAnalysis:
        """Analyze if a message is a follow-up."""
        
        # Check for explicit new-task indicators first
        for pattern in cls.NEW_TASK_PATTERNS:
            if re.search(pattern, message):
                return FollowUpAnalysis(
                    is_follow_up=False,
                    confidence=0.9,
                    previous_task_id=None,
                    suggested_action='new_task',
                    context_inheritance={},
                )
        
        # Check for follow-up patterns
        follow_up_score = 0
        for pattern in cls.FOLLOW_UP_PATTERNS:
            if re.search(pattern, message):
                follow_up_score += 1
        
        # Get recent conversation context
        recent_tasks = cls._get_recent_tasks(conversation_id)
        
        if not recent_tasks:
            # No previous tasks, must be new
            return FollowUpAnalysis(
                is_follow_up=False,
                confidence=1.0,
                previous_task_id=None,
                suggested_action='new_task',
                context_inheritance={},
            )
        
        # Calculate confidence based on patterns and recency
        confidence = min(follow_up_score * 0.3 + 0.4, 0.95)
        
        # Most recent completed or running task
        previous_task = recent_tasks[0] if recent_tasks else None
        
        if follow_up_score >= 1 and previous_task:
            return FollowUpAnalysis(
                is_follow_up=True,
                confidence=confidence,
                previous_task_id=previous_task['id'],
                suggested_action='continue',  # Continue on same branch
                context_inheritance={
                    'branch': previous_task.get('branch'),
                    'modified_files': previous_task.get('modified_files', []),
                    'commit_hash': previous_task.get('commit_hash'),
                    'pr_url': previous_task.get('pr_url'),
                },
            )
        
        # Ambiguous - could be either
        if previous_task and confidence > 0.5:
            return FollowUpAnalysis(
                is_follow_up=True,
                confidence=confidence,
                previous_task_id=previous_task['id'],
                suggested_action='new_branch',  # Create devbuddy/next-* branch
                context_inheritance={
                    'branch': previous_task.get('branch'),
                    'modified_files': previous_task.get('modified_files', []),
                },
            )
        
        # Default to new task
        return FollowUpAnalysis(
            is_follow_up=False,
            confidence=0.6,
            previous_task_id=None,
            suggested_action='new_task',
            context_inheritance={},
        )
    
    @staticmethod
    def _get_recent_tasks(conversation_id: uuid.UUID) -> list:
        """Get recent tasks from conversation."""
        from app.models.conversation import Conversation
        
        # This is synchronous - for async context, this would be awaited
        # For now, return empty and let the service layer handle async
        return []


class FollowUpService:
    """Handle follow-up task creation and continuity."""
    
    def __init__(self):
        self.detector = FollowUpDetector()
    
    async def handle_new_message(
        self,
        conversation_id: uuid.UUID,
        message: str,
    ) -> dict:
        """Process a new message and determine if it's a follow-up.
        
        Returns task creation parameters with follow-up context.
        """
        from app.models.conversation import Conversation, ConversationTask
        
        async with async_session_factory() as db:
            # Get conversation
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await db.execute(conv_stmt)
            conv = conv_result.scalar_one_or_none()
            
            if not conv:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            # Get recent tasks for context
            recent_tasks = await self._get_recent_tasks(db, conversation_id)
            
            # Analyze message
            analysis = self._analyze_with_context(message, recent_tasks)
            
            if analysis.is_follow_up and analysis.previous_task_id:
                # Get the previous task details
                prev_task_stmt = select(ConversationTask).where(
                    ConversationTask.id == analysis.previous_task_id
                )
                prev_task_result = await db.execute(prev_task_stmt)
                prev_task = prev_task_result.scalar_one_or_none()
                
                if prev_task:
                    # Determine branch strategy
                    if analysis.suggested_action == 'continue':
                        # Continue on same branch
                        branch = prev_task.branch
                    elif analysis.suggested_action == 'new_branch':
                        # Create next branch (devbuddy/next-xyz)
                        branch = self._generate_next_branch(prev_task.branch, message)
                    else:
                        # Fallback to new task branch
                        branch = generate_semantic_branch_name(message)
                    
                    # Create the new task with parent link
                    task = ConversationTask(
                        conversation_id=conversation_id,
                        parent_id=prev_task.id,
                        previous_task_id=prev_task.id,
                        title=message[:100],
                        description=message,
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
                        'title': message[:100],
                        'status': 'pending',
                        'created_at': datetime.utcnow().isoformat(),
                    })
                    
                    await db.commit()
                    
                    log.info(
                        "follow_up.task_created",
                        conversation_id=str(conversation_id),
                        task_id=str(task.id),
                        parent_id=str(prev_task.id),
                        branch=branch,
                        confidence=analysis.confidence,
                    )
                    
                    return {
                        'task_id': str(task.id),
                        'is_follow_up': True,
                        'parent_task_id': str(prev_task.id),
                        'branch': branch,
                        'previous_branch': prev_task.branch,
                        'inherited_files': prev_task.modified_files,
                        'confidence': analysis.confidence,
                    }
            
            # Not a follow-up - create new task with semantic branch name
            branch = generate_semantic_branch_name(message)
            
            task = ConversationTask(
                conversation_id=conversation_id,
                title=message[:100],
                description=message,
                branch=branch,
                status='pending',
            )
            
            db.add(task)
            await db.flush()
            
            if not conv.open_tasks:
                conv.open_tasks = []
            conv.open_tasks.append({
                'task_id': str(task.id),
                'title': message[:100],
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
            })
            
            await db.commit()
            
            return {
                'task_id': str(task.id),
                'is_follow_up': False,
                'branch': branch,
                'confidence': analysis.confidence,
            }
    
    async def _get_recent_tasks(self, db, conversation_id: uuid.UUID) -> list:
        """Get recent tasks from conversation."""
        from app.models.conversation import ConversationTask
        
        stmt = (
            select(ConversationTask)
            .where(ConversationTask.conversation_id == conversation_id)
            .order_by(ConversationTask.created_at.desc())
            .limit(5)
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        
        return [
            {
                'id': t.id,
                'title': t.title,
                'branch': t.branch,
                'status': t.status,
                'commit_hash': t.commit_hash,
                'pr_url': t.pr_url,
                'modified_files': t.modified_files,
                'result': t.result,
            }
            for t in tasks
        ]
    
    def _analyze_with_context(
        self,
        message: str,
        recent_tasks: list,
    ) -> FollowUpAnalysis:
        """Analyze message with conversation context."""
        
        # Check for explicit new-task indicators first
        for pattern in FollowUpDetector.NEW_TASK_PATTERNS:
            if re.search(pattern, message):
                return FollowUpAnalysis(
                    is_follow_up=False,
                    confidence=0.9,
                    previous_task_id=None,
                    suggested_action='new_task',
                    context_inheritance={},
                )
        
        # Check for follow-up patterns
        follow_up_score = 0
        for pattern in FollowUpDetector.FOLLOW_UP_PATTERNS:
            if re.search(pattern, message):
                follow_up_score += 1
        
        if not recent_tasks:
            return FollowUpAnalysis(
                is_follow_up=False,
                confidence=1.0,
                previous_task_id=None,
                suggested_action='new_task',
                context_inheritance={},
            )
        
        # Get most recent task
        previous_task = recent_tasks[0]
        confidence = min(follow_up_score * 0.3 + 0.4, 0.95)
        
        if follow_up_score >= 1:
            return FollowUpAnalysis(
                is_follow_up=True,
                confidence=confidence,
                previous_task_id=previous_task['id'],
                suggested_action='continue',
                context_inheritance={
                    'branch': previous_task.get('branch'),
                    'modified_files': previous_task.get('modified_files', []),
                    'commit_hash': previous_task.get('commit_hash'),
                    'pr_url': previous_task.get('pr_url'),
                },
            )
        
        if confidence > 0.5:
            return FollowUpAnalysis(
                is_follow_up=True,
                confidence=confidence,
                previous_task_id=previous_task['id'],
                suggested_action='new_branch',
                context_inheritance={
                    'branch': previous_task.get('branch'),
                    'modified_files': previous_task.get('modified_files', []),
                },
            )
        
        return FollowUpAnalysis(
            is_follow_up=False,
            confidence=0.6,
            previous_task_id=None,
            suggested_action='new_task',
            context_inheritance={},
        )
    
    def _generate_next_branch(self, previous_branch: str, message: str) -> str:
        """Generate a next-* branch name from previous branch and new message."""
        # Generate semantic name from new message
        new_semantic = generate_semantic_branch_name(message)
        
        # Extract category from new semantic name
        if new_semantic.startswith('devbuddy/'):
            parts = new_semantic[9:].split('/', 1)  # Remove devbuddy/ prefix
            if len(parts) == 2:
                category, name = parts
            else:
                category = 'feature'
                name = parts[0]
        else:
            category = 'feature'
            name = new_semantic
        
        # Create follow-up branch name: devbuddy/category/name-follow-up-2
        base = re.sub(r'-[a-f0-9]{8}$', '', name)  # Remove any hash suffix
        base = re.sub(r'-follow-up-\d+$', '', base)  # Remove existing follow-up suffix
        
        return f"devbuddy/{category}/{base}-follow-up"
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        # Remove non-alphanumeric characters except spaces
        text = re.sub(r'[^\w\s-]', '', text)
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text)
        # Convert to lowercase
        return text.lower()[:30]
    
    async def get_task_chain(
        self,
        task_id: uuid.UUID,
    ) -> list:
        """Get the full chain of related tasks (parent -> children)."""
        from app.models.conversation import ConversationTask
        
        async with async_session_factory() as db:
            chain = []
            current_id = task_id
            
            # Walk up the parent chain
            while current_id:
                stmt = select(ConversationTask).where(ConversationTask.id == current_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task:
                    break
                
                chain.insert(0, {
                    'id': str(task.id),
                    'title': task.title,
                    'branch': task.branch,
                    'status': task.status,
                    'commit_hash': task.commit_hash,
                    'pr_url': task.pr_url,
                })
                
                current_id = task.parent_id
            
            return chain


# Singleton instance
follow_up_service = FollowUpService()
