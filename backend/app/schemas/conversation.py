from datetime import datetime

from app.schemas.common import CamelModel


class ConversationListItem(CamelModel):
    id: int
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime | None = None
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationMessageResponse(CamelModel):
    id: int
    role: str
    content: str
    message_type: str
    extra_data: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
