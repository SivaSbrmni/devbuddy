import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from app.models.task import Task, TaskEvent, TaskState
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.task import TaskCreate, TaskStateTransition
from app.services.audit_service import create_audit_log
from app.core.logger import get_logger

logger = get_logger("task_service")

VALID_TRANSITIONS: dict[TaskState, list[TaskState]] = {
    TaskState.PENDING: [TaskState.PLANNING, TaskState.FAILED],
    TaskState.PLANNING: [TaskState.APPROVAL_REQUIRED, TaskState.EXECUTING, TaskState.FAILED],
    TaskState.APPROVAL_REQUIRED: [TaskState.EXECUTING, TaskState.FAILED],
    TaskState.EXECUTING: [TaskState.VALIDATING, TaskState.FAILED, TaskState.QUARANTINED],
    TaskState.VALIDATING: [TaskState.SECURITY_REVIEW, TaskState.HUMAN_REVIEW, TaskState.READY_TO_PUSH, TaskState.FAILED],
    TaskState.SECURITY_REVIEW: [TaskState.HUMAN_REVIEW, TaskState.READY_TO_PUSH, TaskState.QUARANTINED, TaskState.FAILED],
    TaskState.HUMAN_REVIEW: [TaskState.READY_TO_PUSH, TaskState.FAILED],
    TaskState.READY_TO_PUSH: [TaskState.COMPLETED, TaskState.FAILED],
    TaskState.COMPLETED: [],
    TaskState.FAILED: [TaskState.PENDING],
    TaskState.QUARANTINED: [],
}


async def get_or_create_default_tenant(db: AsyncSession) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.slug == "default"))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name="Default Organization", slug="default")
        db.add(tenant)
        await db.flush()
    return tenant


async def get_or_create_user(db: AsyncSession, supabase_id: str, email: str, tenant_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.supabase_id == supabase_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(supabase_id=supabase_id, email=email, tenant_id=tenant_id, last_login=datetime.utcnow())
        db.add(user)
        await db.flush()
    else:
        user.last_login = datetime.utcnow()
        await db.flush()
    return user


async def create_task(db: AsyncSession, data: TaskCreate, user: dict) -> Task:
    tenant = await get_or_create_default_tenant(db)
    db_user = await get_or_create_user(db, user["id"], user["email"], tenant.id)

    task = Task(
        tenant_id=tenant.id,
        created_by=db_user.id,
        title=data.title,
        description=data.description,
        repo_id=data.repo_id,
        branch=data.branch,
        policy_profile=data.policy_profile,
        task_metadata=data.metadata,
        state=TaskState.PENDING,
    )
    db.add(task)
    await db.flush()

    event = TaskEvent(
        task_id=task.id,
        tenant_id=tenant.id,
        event_type="TASK_CREATED",
        from_state=None,
        to_state=TaskState.PENDING.value,
        actor_type="user",
        actor_id=str(db_user.id),
        payload={"title": data.title},
    )
    db.add(event)

    await create_audit_log(
        db,
        tenant_id=tenant.id,
        task_id=task.id,
        event_type="TASK_CREATED",
        actor_type="user",
        actor_id=str(db_user.id),
        action="create_task",
        outcome="success",
        resource_type="task",
        resource_id=str(task.id),
        details={"title": data.title, "policy_profile": data.policy_profile},
    )
    logger.info("task_created", task_id=str(task.id), user_id=str(db_user.id), title=data.title)

    result = await db.execute(
        select(Task)
        .options(selectinload(Task.events))
        .where(Task.id == task.id)
    )
    return result.scalar_one()


async def get_task(db: AsyncSession, task_id: uuid.UUID, tenant_id: uuid.UUID) -> Task | None:
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.events))
        .where(Task.id == task_id, Task.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_tasks(db: AsyncSession, tenant_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Task]:
    result = await db.execute(
        select(Task)
        .where(Task.tenant_id == tenant_id)
        .order_by(desc(Task.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def transition_task_state(
    db: AsyncSession,
    task_id: uuid.UUID,
    tenant_id: uuid.UUID,
    transition: TaskStateTransition,
    actor_id: str,
) -> Task:
    task = await get_task(db, task_id, tenant_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    allowed = VALID_TRANSITIONS.get(task.state, [])
    if transition.to_state not in allowed:
        raise ValueError(f"Invalid transition from {task.state} to {transition.to_state}")

    from_state = task.state
    task.state = transition.to_state
    task.updated_at = datetime.utcnow()
    if transition.to_state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.QUARANTINED):
        task.completed_at = datetime.utcnow()

    event = TaskEvent(
        task_id=task.id,
        tenant_id=tenant_id,
        event_type="STATE_TRANSITION",
        from_state=from_state.value,
        to_state=transition.to_state.value,
        actor_type="user",
        actor_id=actor_id,
        payload={"reason": transition.reason, **transition.payload},
    )
    db.add(event)

    await create_audit_log(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type="TASK_STATE_TRANSITION",
        actor_type="user",
        actor_id=actor_id,
        action="transition_state",
        outcome="success",
        resource_type="task",
        resource_id=str(task_id),
        details={"from": from_state.value, "to": transition.to_state.value},
    )
    logger.info("task_state_transition", task_id=str(task_id), from_state=from_state.value, to_state=transition.to_state.value)

    result = await db.execute(
        select(Task)
        .options(selectinload(Task.events))
        .where(Task.id == task_id)
    )
    return result.scalar_one()
