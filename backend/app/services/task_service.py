from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskLog
from app.schemas.common import PaginatedResponse
from app.schemas.task import TaskDetailResponse, TaskListItem, TaskLogItem


async def get_tasks(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    task_type: str | None = None,
) -> PaginatedResponse[TaskListItem]:
    query = select(Task).where(Task.user_id == user_id)
    count_query = select(func.count()).select_from(Task).where(Task.user_id == user_id)

    if task_type:
        query = query.where(Task.type == task_type)
        count_query = count_query.where(Task.type == task_type)

    query = query.order_by(Task.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query)
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        params = t.params if t.params else None
        summary = t.result_summary if t.result_summary else None
        items.append(
            TaskListItem(
                id=t.id,
                type=t.type,
                status=t.status,
                params=params,
                result_summary=summary,
                created_at=str(t.created_at),
                updated_at=str(t.updated_at) if t.updated_at else None,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


async def get_task_detail(db: AsyncSession, task_id: int) -> TaskDetailResponse | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        return None

    logs_result = await db.execute(
        select(TaskLog)
        .where(TaskLog.task_id == task_id)
        .order_by(TaskLog.step_number)
    )
    logs = logs_result.scalars().all()

    params = task.params if task.params else None
    summary = task.result_summary if task.result_summary else None

    return TaskDetailResponse(
        id=task.id,
        type=task.type,
        status=task.status,
        params=params,
        result_summary=summary,
        logs=[
            TaskLogItem(
                id=log.id,
                step_number=log.step_number,
                step_name=log.step_name,
                status=log.status,
                message=log.message,
                progress=log.progress,
            )
            for log in logs
        ],
        created_at=str(task.created_at),
        updated_at=str(task.updated_at) if task.updated_at else None,
    )
