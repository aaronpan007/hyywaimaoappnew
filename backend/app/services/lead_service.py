import io

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl import Workbook

from app.models.lead import Lead
from app.models.outreach_email import OutreachEmail
from app.schemas.common import PaginatedResponse
from app.schemas.lead import LeadResponse


async def get_leads(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    country: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedResponse[LeadResponse]:
    # Only show leads from tasks belonging to this user
    from app.models.task import Task

    task_ids_query = select(Task.id).where(Task.user_id == user_id)
    query = select(Lead).where(Lead.task_id.in_(task_ids_query))
    count_query = (
        select(func.count())
        .select_from(Lead)
        .where(Lead.task_id.in_(task_ids_query))
    )

    if search:
        search_filter = Lead.company_name.ilike(f"%{search}%") | Lead.email.ilike(
            f"%{search}%"
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if country:
        query = query.where(Lead.country == country)
        count_query = count_query.where(Lead.country == country)

    # Sort
    sort_col = getattr(Lead, sort_by, Lead.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    leads = result.scalars().all()

    items = []
    for lead in leads:
        # Get latest email status for this lead
        email_result = await db.execute(
            select(OutreachEmail.send_status)
            .where(OutreachEmail.lead_id == lead.id)
            .order_by(OutreachEmail.created_at.desc())
            .limit(1)
        )
        email_status = email_result.scalar() or "draft"

        items.append(
            LeadResponse(
                id=lead.id,
                company_name=lead.company_name,
                website=lead.website,
                country=lead.country,
                industry=lead.industry,
                company_role=lead.company_role,
                contact_name=lead.contact_name,
                email=lead.email,
                phone=lead.phone,
                ai_summary=lead.ai_summary,
                business_match=lead.business_match,
                outreach_suggestion=lead.outreach_suggestion,
                match_score=lead.match_score,
                email_status=email_status,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


async def export_leads_xlsx(db: AsyncSession, user_id: int) -> bytes:
    from app.models.task import Task

    task_ids_query = select(Task.id).where(Task.user_id == user_id)
    result = await db.execute(
        select(Lead)
        .where(Lead.task_id.in_(task_ids_query))
        .order_by(Lead.match_score.desc())
    )
    leads = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    headers = [
        "Company Name", "Website", "Country", "Industry",
        "Contact Name", "Email", "Phone", "Match Score",
        "AI Summary", "Business Match",
    ]
    ws.append(headers)

    for lead in leads:
        ws.append([
            lead.company_name,
            lead.website,
            lead.country,
            lead.industry,
            lead.contact_name,
            lead.email,
            lead.phone,
            lead.match_score,
            lead.ai_summary,
            lead.business_match,
        ])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
