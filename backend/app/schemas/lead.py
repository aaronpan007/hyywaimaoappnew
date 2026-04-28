from app.schemas.common import CamelModel


class LeadResponse(CamelModel):
    id: int
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
    email_status: str = "draft"


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
