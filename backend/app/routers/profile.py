from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.schemas.profile import CompanyProfileResponse
from app.services import profile_service

router = APIRouter()


@router.get("/profile")
async def get_profile(db: DBSession, user: CurrentUser):
    profile = await profile_service.get_current_profile(db, user)
    if profile is None:
        return {"detail": "No profile found"}
    return profile.model_dump(by_alias=True)


@router.post("/profile", response_model=CompanyProfileResponse)
async def create_profile(db: DBSession, user: CurrentUser, profile_data: dict):
    return await profile_service.create_profile(db, user, profile_data)


@router.put("/profile/{profile_id}", response_model=CompanyProfileResponse)
async def update_profile(db: DBSession, profile_id: int, profile_data: dict):
    profile = await profile_service.update_profile(db, profile_id, profile_data)
    if profile is None:
        return {"detail": "Profile not found"}
    return profile
