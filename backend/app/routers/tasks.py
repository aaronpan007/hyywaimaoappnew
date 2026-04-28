from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, DBSession
from app.schemas.chat import StartPipelineRequest
from app.schemas.common import PaginatedResponse
from app.schemas.task import TaskDetailResponse, TaskListItem
from app.services import chat_service, task_manager, task_service

router = APIRouter()


@router.get("/tasks", response_model=PaginatedResponse[TaskListItem])
async def get_tasks(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
):
    return await task_service.get_tasks(db, user, page, page_size, type)


@router.get("/tasks/running")
async def get_running_task(db: DBSession, user_id: CurrentUser):
    """Get the currently running task for the user (for page reload recovery).

    Also checks heartbeat — tasks with stale heartbeats are not returned.
    """
    import time

    from sqlalchemy import select
    from app.models.task import Task

    result = await db.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.status == "running")
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    t = result.scalar_one_or_none()
    if t is None:
        return {"taskId": None}

    # Check if the task actually has a live heartbeat
    last_hb = task_manager.task_heartbeats.get(t.id)
    if last_hb is not None:
        if time.monotonic() - last_hb > task_manager.HEARTBEAT_TIMEOUT:
            # Stale — mark as failed and don't return
            await task_manager.mark_stale_tasks(db)
            return {"taskId": None}

    return {"taskId": t.id, "type": t.type, "params": t.params}


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: int, db: DBSession, user_id: CurrentUser):
    """Stop a running or pending task."""
    from app.models.task import Task

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    if task.status not in ("running", "pending"):
        raise HTTPException(400, f"Cannot stop task with status '{task.status}'")

    await task_manager.cancel_task(task_id, db)
    return {"status": "cancelled"}


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(db: DBSession, task_id: int):
    detail = await task_service.get_task_detail(db, task_id)
    if detail is None:
        return {"detail": "Task not found"}
    return detail


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: int, db: DBSession, user_id: CurrentUser
):
    """SSE reconnect endpoint: resume task progress from DB."""
    from app.models.task import Task

    task = await db.get(Task, task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(404, "Task not found")

    return StreamingResponse(
        chat_service.stream_task_progress(task_id, db),
        media_type="text/event-stream",
        headers=chat_service.SSE_HEADERS,
    )


@router.post("/tasks/start")
async def start_pipeline(
    req: StartPipelineRequest, db: DBSession, user_id: CurrentUser
):
    """Start a pipeline after user confirms search parameters.

    Creates a Task, launches the pipeline, and returns SSE stream.
    """
    params = {
        "industry": req.industry,
        "country": req.country,
        "keywords": req.keywords,
        "num": req.num,
    }

    result = await chat_service.start_pipeline(params, db, user_id)

    return StreamingResponse(
        chat_service.stream_task_progress(result["task_id"], db),
        media_type="text/event-stream",
        headers=chat_service.SSE_HEADERS,
    )
