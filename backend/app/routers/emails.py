from fastapi import APIRouter, Query

from app.dependencies import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.email import (
    GenerateEmailsRequest,
    OutreachEmailResponse,
    SendEmailsRequest,
)
from app.services import email_service

router = APIRouter()


@router.get("/emails", response_model=PaginatedResponse[OutreachEmailResponse])
async def get_emails(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await email_service.get_emails(db, user, page, page_size)


@router.post("/emails/generate")
async def generate_emails(db: DBSession, user: CurrentUser, req: GenerateEmailsRequest):
    return await email_service.generate_emails_stub(db, user, req.lead_ids)


@router.post("/emails/send")
async def send_emails(db: DBSession, user: CurrentUser, req: SendEmailsRequest):
    return await email_service.send_emails_stub(db, user, req.email_ids)
