from app.schemas.common import CamelModel


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
