from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.schemas.settings import (
    EmailSettingsResponse,
    GeneratePrefixRequest,
    GeneratePrefixResponse,
    UpdateSettingsRequest,
)
from app.services import settings_service

router = APIRouter()


@router.get("/settings", response_model=EmailSettingsResponse)
async def get_settings(db: DBSession, user: CurrentUser):
    return await settings_service.get_settings(db, user)


@router.put("/settings", response_model=EmailSettingsResponse)
async def update_settings(db: DBSession, user: CurrentUser, req: UpdateSettingsRequest):
    return await settings_service.update_settings(db, user, req)


@router.post("/settings/generate-prefix", response_model=GeneratePrefixResponse)
async def generate_prefix(req: GeneratePrefixRequest):
    prefixes = settings_service.generate_prefix(req.company_name)
    return GeneratePrefixResponse(prefixes=prefixes)
