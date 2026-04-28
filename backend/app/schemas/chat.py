from typing import Any, Literal

from app.schemas.common import CamelModel


class ChatRequest(CamelModel):
    message: str
    conversation_id: str | None = None


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
    industry: str
    country: str
    keywords: list[str]
    num: int
