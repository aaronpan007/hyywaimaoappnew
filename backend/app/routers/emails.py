from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.dependencies import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.email import (
    GenerateEmailsRequest,
    OutreachEmailResponse,
    SendEmailsRequest,
    UpdateLeadEmailRequest,
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
    return await email_service.send_emails_stub(
        db,
        user,
        req.email_ids,
        lead_ids=req.lead_ids,
        delay_min=req.delay_min,
        delay_max=req.delay_max,
        daily_limit=req.daily_limit,
        dry_run=req.dry_run,
        send_mode=req.send_mode,
    )


@router.post("/emails/resend/webhook")
async def resend_webhook(request: Request, db: DBSession):
    raw_body = await request.body()
    headers = {key: value for key, value in request.headers.items()}
    if not email_service.verify_resend_webhook_signature(raw_body, headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    return await email_service.handle_resend_webhook(db, payload)


@router.patch("/emails/leads/{lead_id}")
async def update_lead_email(
    lead_id: int,
    req: UpdateLeadEmailRequest,
    db: DBSession,
    user: CurrentUser,
):
    return await email_service.update_latest_email_for_lead(db, user, lead_id, req)


@router.get("/emails/{task_id}/export")
async def export_emails(task_id: int, db: DBSession, user: CurrentUser):
    """Export leads + emails for a task as Excel."""
    from urllib.parse import quote

    xlsx_bytes = await email_service.export_emails_xlsx(db, user, task_id=task_id)
    filename = f"emails_task_{task_id}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
