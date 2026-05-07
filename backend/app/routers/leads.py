from fastapi import APIRouter, Query
from pydantic import BaseModel
from fastapi.responses import Response

from app.dependencies import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.lead import LeadEmailResponse, LeadResponse, UpdateLeadRequest
from app.services import lead_service

router = APIRouter()


class DeleteLeadsRequest(BaseModel):
    lead_ids: list[int]


@router.get("/leads", response_model=PaginatedResponse[LeadResponse])
async def get_leads(
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=100),
    pageSize: int | None = Query(None, ge=1, le=100),
    task_id: int | None = Query(None),
    taskId: int | None = Query(None),
    search: str | None = Query(None),
    country: str | None = Query(None),
    industry: str | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    minScore: float | None = Query(None, ge=0, le=100),
    sort_by: str | None = Query(None),
    sortBy: str | None = Query(None),
    sort_order: str = Query("desc"),
    sortOrder: str | None = Query(None),
):
    resolved_page_size = pageSize or page_size or 20
    resolved_task_id = taskId or task_id
    resolved_min_score = minScore if minScore is not None else min_score
    resolved_sort_by = sortBy or sort_by or "created_at"
    resolved_sort_order = sortOrder or sort_order

    return await lead_service.get_leads(
        db,
        user,
        page,
        resolved_page_size,
        resolved_task_id,
        search,
        country,
        industry,
        resolved_min_score,
        resolved_sort_by,
        resolved_sort_order,
    )


@router.delete("/leads")
async def delete_leads(req: DeleteLeadsRequest, db: DBSession, user: CurrentUser):
    deleted = await lead_service.delete_leads(db, user, req.lead_ids)
    return {"deleted": deleted}


@router.patch("/leads/{lead_id}")
async def update_lead(req: UpdateLeadRequest, lead_id: int, db: DBSession, user: CurrentUser):
    await lead_service.update_lead(db, user, lead_id, req)
    return {"ok": True}


@router.get("/leads/{task_id}/emails", response_model=PaginatedResponse[LeadEmailResponse])
async def get_leads_with_emails(
    task_id: int,
    db: DBSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    pageSize: int | None = Query(None, ge=1, le=100),
    page_size: int | None = Query(None, ge=1, le=100),
    search: str | None = Query(None),
):
    """Get leads with their emails for a specific email-craft task."""
    resolved_page_size = pageSize or page_size or 20
    return await lead_service.get_leads_with_emails(
        db, user, task_id, page, resolved_page_size, search
    )


@router.get("/leads/{lead_id}/export")
async def export_leads(
    db: DBSession,
    user: CurrentUser,
    lead_id: int = 0,
    task_id: int | None = Query(None),
    taskId: int | None = Query(None),
    search: str | None = Query(None),
    country: str | None = Query(None),
    industry: str | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    minScore: float | None = Query(None, ge=0, le=100),
):
    # lead_id is kept for backward compatibility. Prefer taskId/task_id.
    resolved_task_id = taskId or task_id or (lead_id if lead_id else None)
    resolved_min_score = minScore if minScore is not None else min_score

    xlsx_data = await lead_service.export_leads_xlsx(
        db,
        user,
        task_id=resolved_task_id,
        search=search,
        country=country,
        industry=industry,
        min_score=resolved_min_score,
    )
    return Response(
        content=xlsx_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads.xlsx"},
    )
