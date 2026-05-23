import uuid
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.task import TaskCreate, TaskOut, TaskListOut, TaskStateTransition
from app.services import task_service
from app.services.task_service import get_or_create_default_tenant, get_or_create_user
from app.core.logger import get_logger

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = get_logger("tasks_api")

_ws_connections: dict[str, list[WebSocket]] = {}


@router.post("", response_model=TaskOut)
async def create_task(
    data: TaskCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.create_task(db, data, user)
    await _broadcast_event(str(task.id), {"type": "TASK_CREATED", "state": task.state.value})
    return task


@router.get("", response_model=list[TaskListOut])
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await get_or_create_default_tenant(db)
    return await task_service.list_tasks(db, tenant.id, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await get_or_create_default_tenant(db)
    task = await task_service.get_task(db, task_id, tenant.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}/state", response_model=TaskOut)
async def transition_state(
    task_id: uuid.UUID,
    transition: TaskStateTransition,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await get_or_create_default_tenant(db)
    try:
        task = await task_service.transition_task_state(db, task_id, tenant.id, transition, user["id"])
        await _broadcast_event(str(task_id), {"type": "STATE_TRANSITION", "state": task.state.value, "from": transition.to_state.value})
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.websocket("/{task_id}/stream")
async def task_stream(task_id: str, websocket: WebSocket):
    await websocket.accept()
    if task_id not in _ws_connections:
        _ws_connections[task_id] = []
    _ws_connections[task_id].append(websocket)
    logger.info("ws_client_connected", task_id=task_id)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "PING", "task_id": task_id, "timestamp": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        _ws_connections[task_id].remove(websocket)
        logger.info("ws_client_disconnected", task_id=task_id)


async def _broadcast_event(task_id: str, event: dict):
    if task_id not in _ws_connections:
        return
    payload = json.dumps({
        "type": "TASK_EVENT",
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
    })
    dead = []
    for ws in _ws_connections.get(task_id, []):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_connections[task_id].remove(ws)
