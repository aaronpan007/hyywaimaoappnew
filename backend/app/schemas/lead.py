from pydantic import BaseModel

from app.schemas.common import CamelModel


class UpdateLeadRequest(BaseModel):
    contact_name: str | None = None
    email: str | None = None
    user_note: str | None = None

    model_config = {"extra": "forbid"}


class LeadResponse(CamelModel):
    id: int
    source_task_id: int | None = None
    source_list: str = ""
    user_note: str = ""
    company_name: str
    website: str
    country: str
    industry: str
    company_role: str = ""
    contact_name: str
    email: str
    phone: str = ""
    ai_summary: str = ""
    business_match: str = ""
    outreach_suggestion: str = ""
    match_score: float
    email_status: str = "unwritten"
    email_subject: str = ""
    email_body: str = ""


class LeadDetailResponse(CamelModel):
    id: int
    company_name: str
    website: str
    country: str
    industry: str
    company_role: str
    contact_name: str
    email: str
    phone: str
    ai_summary: str
    business_match: str
    outreach_suggestion: str
    match_score: float
    created_at: str


class LeadEmailResponse(CamelModel):
    id: int
    company_name: str
    website: str
    country: str
    industry: str
    company_role: str = ""
    contact_name: str
    email: str
    phone: str = ""
    match_score: float
    email_subject: str = ""
    email_body: str = ""
