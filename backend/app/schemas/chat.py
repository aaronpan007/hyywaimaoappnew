from typing import Any, Literal

from app.schemas.common import CamelModel


class FileUpload(CamelModel):
    filename: str
    data: str  # base64


class ChatRequest(CamelModel):
    message: str
    conversation_id: int | None = None
    mode: str | None = None
    images: list[str] | None = None
    files: list[FileUpload] | None = None


class ThinkingEvent(CamelModel):
    pass


class ConfigRequiredEvent(CamelModel):
    missing_fields: list[str]


class SuggestionEvent(CamelModel):
    text: str
    action: str


class PipelineStartedEvent(CamelModel):
    task_id: int
    type: str
    params: dict[str, Any]


class StepUpdateEvent(CamelModel):
    task_id: int
    step: int
    name: str
    status: Literal["completed", "running", "pending"]
    progress: int
    message: str


class ResultEvent(CamelModel):
    task_id: int
    type: Literal["callout"]
    callout: dict[str, Any]


class DoneEvent(CamelModel):
    task_id: int | None = None


class StartPipelineRequest(CamelModel):
    industry: str = ""
    country: str = ""
    keywords: list[str] = []
    customer_types: list[str] | None = None
    num: int = 20
    confirm_type: str = "customer_acquisition"
    language: str = "en"
    files: list[FileUpload] | None = None
    lead_ids: list[int] | None = None
    source_task_id: int | None = None
    conversation_id: int | None = None
    user_requirements: str = ""
    delay_min: int = 60
    delay_max: int = 120
    daily_limit: int = 50
    dry_run: bool = False
    send_mode: str = "auto"
