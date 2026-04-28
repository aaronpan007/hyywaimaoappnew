from app.schemas.common import CamelModel


class TaskLogItem(CamelModel):
    id: int
    step_number: int
    step_name: str
    status: str
    message: str
    progress: int


class TaskListItem(CamelModel):
    id: int
    type: str
    status: str
    params: dict | None = None
    result_summary: dict | None = None
    created_at: str
    updated_at: str | None = None
    ended_at: str | None = None
    cancelled: bool = False


class TaskDetailResponse(CamelModel):
    id: int
    type: str
    status: str
    params: dict | None = None
    result_summary: dict | None = None
    logs: list[TaskLogItem]
    created_at: str
    updated_at: str | None = None
    ended_at: str | None = None
    cancelled: bool = False
