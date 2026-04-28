from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.dependencies import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.lead import LeadResponse
from app.services import lead_service

router = APIRouter()


@router.get("/leads", response_model=PaginatedResponse[LeadResponse])
async def get_leads(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    country: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
):
    return await lead_service.get_leads(
        db, user, page, page_size, search, country, sort_by, sort_order
    )


@router.get("/leads/{lead_id}/export")
async def export_leads(db: DBSession, user: CurrentUser, lead_id: int = 0):
    # lead_id in URL is ignored — export all leads for user
    xlsx_data = await lead_service.export_leads_xlsx(db, user)
    return Response(
        content=xlsx_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads.xlsx"},
    )
