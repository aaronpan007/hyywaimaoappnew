from app.schemas.common import CamelModel
from pydantic import BaseModel


class UpdateLeadEmailRequest(BaseModel):
    email_subject: str | None = None
    email_body: str | None = None

    model_config = {"extra": "forbid"}


class OutreachEmailResponse(CamelModel):
    id: int
    lead_id: int
    lead_company_name: str = ""
    email_subject: str
    email_body: str
    send_status: str
    sent_at: str | None = None
    created_at: str


class GenerateEmailsRequest(CamelModel):
    lead_ids: list[int] = []


class SendEmailsRequest(CamelModel):
    email_ids: list[int] = []
    lead_ids: list[int] = []
    delay_min: int = 60
    delay_max: int = 120
    daily_limit: int = 50
    dry_run: bool = False
    send_mode: str = "auto"
