"""Conversation API - server-side persistence replacing localStorage.

This module provides CRUD operations for conversations, messages, and tasks,
enabling device-independent access and real-time synchronization.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=255)
    repository_url: Optional[str] = None
    repository_name: Optional[str] = None
    repository_owner: Optional[str] = None
    branch: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = None
    current_goal: Optional[str] = None
    status: Optional[str] = None  # active, archived, completed


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    metadata: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    metadata: dict
    is_complete: bool
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    parent_task_id: Optional[uuid.UUID] = None
    previous_task_id: Optional[uuid.UUID] = None
    branch: str


class TaskUpdate(BaseModel):
    status: Optional[str] = None  # pending, running, completed, error
    commit_hash: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    result: Optional[dict] = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    repository_url: Optional[str]
    repository_name: Optional[str]
    repository_owner: Optional[str]
    branch: Optional[str]
    summary: str
    current_goal: str
    completed_tasks: List[dict]
    open_tasks: List[dict]
    modified_files: List[str]
    important_decisions: List[dict]
    status: str
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationListResponse(BaseModel):
    id: uuid.UUID
    title: str
    repository_name: Optional[str]
    status: str
    last_message_at: Optional[datetime]
    message_count: int
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse]


# ─── Conversation CRUD ───────────────────────────────────────────────────────

@router.post("", response_model=ConversationResponse)
async def create_conversation(
    req: ConversationCreate,
    user: User = Depends(get_current_user),
) -> ConversationResponse:
    """Create a new conversation."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation

    async with async_session_factory() as db:
        conv = Conversation(
            user_id=user.id,
            title=req.title,
            repository_url=req.repository_url,
            repository_name=req.repository_name,
            repository_owner=req.repository_owner,
            branch=req.branch,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

        return ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            repository_url=conv.repository_url,
            repository_name=conv.repository_name,
            repository_owner=conv.repository_owner,
            branch=conv.branch,
            summary=conv.summary,
            current_goal=conv.current_goal,
            completed_tasks=conv.completed_tasks,
            open_tasks=conv.open_tasks,
            modified_files=conv.modified_files,
            important_decisions=conv.important_decisions,
            status=conv.status,
            last_message_at=conv.last_message_at,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )


@router.get("", response_model=List[ConversationListResponse])
async def list_conversations(
    status: Optional[str] = Query(None, description="Filter by status"),
    repo_url: Optional[str] = Query(None, description="Filter by repository"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> List[ConversationListResponse]:
    """List user's conversations with optional filters."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation
    from sqlalchemy import select, func

    async with async_session_factory() as db:
        stmt = select(Conversation).where(Conversation.user_id == user.id)

        if status:
            stmt = stmt.where(Conversation.status == status)
        if repo_url:
            stmt = stmt.where(Conversation.repository_url == repo_url)

        stmt = stmt.order_by(Conversation.last_message_at.desc().nullslast())
        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        conversations = result.scalars().all()

        # Get message counts
        conv_ids = [c.id for c in conversations]
        from app.models.conversation import Message
        count_stmt = (
            select(Message.conversation_id, func.count(Message.id))
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        count_result = await db.execute(count_stmt)
        counts = {row[0]: row[1] for row in count_result.all()}

        return [
            ConversationListResponse(
                id=c.id,
                title=c.title,
                repository_name=c.repository_name,
                status=c.status,
                last_message_at=c.last_message_at,
                message_count=counts.get(c.id, 0),
                created_at=c.created_at,
            )
            for c in conversations
        ]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    include_messages: bool = Query(True),
    user: User = Depends(get_current_user),
) -> ConversationDetailResponse:
    """Get full conversation with messages."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select, func

    async with async_session_factory() as db:
        # Get conversation
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get message count
        count_stmt = (
            select(func.count(Message.id))
            .where(Message.conversation_id == conversation_id)
        )
        count_result = await db.execute(count_stmt)
        message_count = count_result.scalar()

        messages = []
        if include_messages:
            msg_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            msg_result = await db.execute(msg_stmt)
            messages = [
                MessageResponse(
                    id=m.id,
                    conversation_id=m.conversation_id,
                    role=m.role,
                    content=m.content,
                    metadata=m.metadata,
                    is_complete=m.is_complete,
                    created_at=m.created_at,
                )
                for m in msg_result.scalars().all()
            ]

        return ConversationDetailResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            repository_url=conv.repository_url,
            repository_name=conv.repository_name,
            repository_owner=conv.repository_owner,
            branch=conv.branch,
            summary=conv.summary,
            current_goal=conv.current_goal,
            completed_tasks=conv.completed_tasks,
            open_tasks=conv.open_tasks,
            modified_files=conv.modified_files,
            important_decisions=conv.important_decisions,
            status=conv.status,
            last_message_at=conv.last_message_at,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=message_count,
            messages=messages,
        )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    req: ConversationUpdate,
    user: User = Depends(get_current_user),
) -> ConversationResponse:
    """Update conversation metadata."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if req.title is not None:
            conv.title = req.title
        if req.summary is not None:
            conv.summary = req.summary
        if req.current_goal is not None:
            conv.current_goal = req.current_goal
        if req.status is not None:
            conv.status = req.status

        conv.version += 1  # Optimistic locking
        await db.commit()
        await db.refresh(conv)

        return ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            repository_url=conv.repository_url,
            repository_name=conv.repository_name,
            repository_owner=conv.repository_owner,
            branch=conv.branch,
            summary=conv.summary,
            current_goal=conv.current_goal,
            completed_tasks=conv.completed_tasks,
            open_tasks=conv.open_tasks,
            modified_files=conv.modified_files,
            important_decisions=conv.important_decisions,
            status=conv.status,
            last_message_at=conv.last_message_at,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,  # Will be populated if needed
        )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
) -> dict:
    """Delete a conversation and all its messages."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation
    from sqlalchemy import select

    async with async_session_factory() as db:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await db.delete(conv)
        await db.commit()

        return {"deleted": True, "id": str(conversation_id)}


# ─── Message CRUD ────────────────────────────────────────────────────────────

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(
    conversation_id: uuid.UUID,
    req: MessageCreate,
    user: User = Depends(get_current_user),
) -> MessageResponse:
    """Add a message to a conversation."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select

    async with async_session_factory() as db:
        # Verify ownership
        conv_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        conv_result = await db.execute(conv_stmt)
        conv = conv_result.scalar_one_or_none()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Create message
        msg = Message(
            conversation_id=conversation_id,
            role=req.role,
            content=req.content,
            metadata=req.metadata,
        )
        db.add(msg)

        # Update conversation
        conv.last_message_at = datetime.utcnow()
        conv.version += 1

        await db.commit()
        await db.refresh(msg)

        return MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            metadata=msg.metadata,
            is_complete=msg.is_complete,
            created_at=msg.created_at,
        )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> List[MessageResponse]:
    """Get messages in a conversation."""
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation, Message
    from sqlalchemy import select

    async with async_session_factory() as db:
        # Verify ownership
        conv_stmt = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
        conv_result = await db.execute(conv_stmt)
        if not conv_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Conversation not found")

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        messages = result.scalars().all()

        return [
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                metadata=m.metadata,
                is_complete=m.is_complete,
                created_at=m.created_at,
            )
            for m in messages
        ]


# ─── Sync Endpoint ───────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    last_sync_at: Optional[datetime] = None
    client_conversations: List[dict] = Field(default_factory=list)


class SyncResponse(BaseModel):
    updated_conversations: List[ConversationResponse]
    deleted_ids: List[uuid.UUID]
    server_timestamp: datetime


@router.post("/sync", response_model=SyncResponse)
async def sync_conversations(
    req: SyncRequest,
    user: User = Depends(get_current_user),
) -> SyncResponse:
    """Sync conversations between client and server.

    Client sends its last known state, server returns:
    - New/updated conversations since last_sync_at
    - IDs of conversations deleted on server
    - Current server timestamp for next sync
    """
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation
    from sqlalchemy import select

    async with async_session_factory() as db:
        # Get all conversations updated since last sync
        stmt = select(Conversation).where(Conversation.user_id == user.id)

        if req.last_sync_at:
            stmt = stmt.where(Conversation.updated_at > req.last_sync_at)

        stmt = stmt.order_by(Conversation.updated_at.desc())

        result = await db.execute(stmt)
        conversations = result.scalars().all()

        # TODO: Detect deleted conversations
        # This requires tombstones or a deleted_conversations table
        deleted_ids = []

        return SyncResponse(
            updated_conversations=[
                ConversationResponse(
                    id=c.id,
                    user_id=c.user_id,
                    title=c.title,
                    repository_url=c.repository_url,
                    repository_name=c.repository_name,
                    repository_owner=c.repository_owner,
                    branch=c.branch,
                    summary=c.summary,
                    current_goal=c.current_goal,
                    completed_tasks=c.completed_tasks,
                    open_tasks=c.open_tasks,
                    modified_files=c.modified_files,
                    important_decisions=c.important_decisions,
                    status=c.status,
                    last_message_at=c.last_message_at,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    message_count=0,
                )
                for c in conversations
            ],
            deleted_ids=deleted_ids,
            server_timestamp=datetime.utcnow(),
        )


# ─── SSE for Real-Time Updates ────────────────────────────────────────────────

class SSEManager:
    """Manage SSE connections for real-time sync."""

    def __init__(self):
        self.active_connections: dict[uuid.UUID, list[asyncio.Queue]] = {}

    def connect(self, user_id: uuid.UUID) -> asyncio.Queue:
        """Create a new queue for a user's SSE connection."""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        queue = asyncio.Queue()
        self.active_connections[user_id].append(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue, user_id: uuid.UUID):
        """Remove a queue when client disconnects."""
        if user_id in self.active_connections:
            if queue in self.active_connections[user_id]:
                self.active_connections[user_id].remove(queue)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: uuid.UUID, message: dict):
        """Send a message to all active SSE connections for a user."""
        if user_id in self.active_connections:
            for queue in self.active_connections[user_id]:
                try:
                    await queue.put(message)
                except Exception:
                    pass


sse_manager = SSEManager()


@router.get("/sse")
async def sse_endpoint(
    token: str = Query(...),
):
    """SSE endpoint for real-time conversation updates."""
    # Manually validate token
    from app.core.security import decode_token
    from app.db.session import async_session_factory
    from app.models.user import User
    from sqlalchemy import select

    payload = decode_token(token)
    if not payload:
        return StreamingResponse(
            iter([b"data: {\"type\": \"error\", \"message\": \"Invalid token\"}\n\n"]),
            media_type="text/event-stream",
        )

    email = payload.get("email") or payload.get("sub")
    if not email:
        return StreamingResponse(
            iter([b"data: {\"type\": \"error\", \"message\": \"Token missing user identification\"}\n\n"]),
            media_type="text/event-stream",
        )

    async with async_session_factory() as db:
        stmt = select(User).where(User.email == email.lower())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return StreamingResponse(
                iter([b"data: {\"type\": \"error\", \"message\": \"User not found\"}\n\n"]),
                media_type="text/event-stream",
            )

    queue = sse_manager.connect(user.id)

    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            
            while True:
                # Wait for messages from the queue
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            sse_manager.disconnect(queue, user.id)
        except Exception:
            sse_manager.disconnect(queue, user.id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
