from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.outreach_email import OutreachEmail
from app.schemas.common import PaginatedResponse
from app.schemas.email import OutreachEmailResponse


async def get_emails(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[OutreachEmailResponse]:
    from app.models.task import Task
    from sqlalchemy import func

    task_ids_query = select(Task.id).where(Task.user_id == user_id)
    query = (
        select(OutreachEmail)
        .where(OutreachEmail.task_id.in_(task_ids_query))
        .order_by(OutreachEmail.created_at.desc())
    )
    count_query = (
        select(func.count())
        .select_from(OutreachEmail)
        .where(OutreachEmail.task_id.in_(task_ids_query))
    )

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    emails = result.scalars().all()

    items = []
    for em in emails:
        # Get lead company name
        lead_result = await db.execute(select(Lead.company_name).where(Lead.id == em.lead_id))
        lead_company = lead_result.scalar() or ""

        items.append(
            OutreachEmailResponse(
                id=em.id,
                lead_id=em.lead_id,
                lead_company_name=lead_company,
                email_subject=em.email_subject,
                email_body=em.email_body,
                send_status=em.send_status,
                sent_at=str(em.sent_at) if em.sent_at else None,
                created_at=str(em.created_at),
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


async def generate_emails_stub(
    db: AsyncSession,
    user_id: int,
    lead_ids: list[int],
) -> dict:
    """Phase 1 stub — Phase 2 TODO: call email-craft Pipeline."""
    return {
        "status": "stub",
        "message": f"Would generate emails for {len(lead_ids)} leads. Phase 2: will call email-craft Pipeline.",
        "lead_ids": lead_ids,
    }


async def send_emails_stub(
    db: AsyncSession,
    user_id: int,
    email_ids: list[int],
) -> dict:
    """Phase 1 stub — Phase 2 TODO: call email-blast Pipeline."""
    return {
        "status": "stub",
        "message": f"Would send {len(email_ids)} emails. Phase 2: will call email-blast Pipeline.",
        "email_ids": email_ids,
    }
