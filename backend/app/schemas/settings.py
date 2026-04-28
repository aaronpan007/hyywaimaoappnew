from app.schemas.common import CamelModel


class EmailSettingsResponse(CamelModel):
    sender_name: str
    reply_to_email: str
    from_email_prefix: str
    mail_domain: str
    configured_at: str | None = None


class UpdateSettingsRequest(CamelModel):
    sender_name: str | None = None
    reply_to_email: str | None = None
    from_email_prefix: str | None = None


class GeneratePrefixRequest(CamelModel):
    company_name: str


class GeneratePrefixResponse(CamelModel):
    prefixes: list[str]
