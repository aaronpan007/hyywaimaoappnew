from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_profile import CompanyProfile
from app.schemas.profile import CaseStudy, CompanyProfileResponse


def _profile_data_to_response(
    cp: CompanyProfile,
) -> CompanyProfileResponse:
    profile = cp.profile_data if isinstance(cp.profile_data, dict) else {}

    case_studies = []
    for cs in profile.get("caseStudies", []):
        case_studies.append(
            CaseStudy(project=cs.get("project", ""), description=cs.get("description", ""))
        )

    return CompanyProfileResponse(
        id=cp.id,
        company_name=cp.company_name or profile.get("companyName", ""),
        industry=profile.get("industry", ""),
        website=profile.get("website", ""),
        established=profile.get("established", ""),
        employees=profile.get("employees", ""),
        certifications=profile.get("certifications", ""),
        cooperation_models=profile.get("cooperationModels", ""),
        products=profile.get("products", []),
        competencies=profile.get("competencies", []),
        case_studies=case_studies,
        collected_at=str(cp.created_at),
        is_current=cp.is_current,
    )


async def get_current_profile(
    db: AsyncSession, user_id: int
) -> CompanyProfileResponse | None:
    result = await db.execute(
        select(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)
        .order_by(CompanyProfile.updated_at.desc())
        .limit(1)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        return None
    return _profile_data_to_response(cp)


async def create_profile(
    db: AsyncSession, user_id: int, profile_data: dict
) -> CompanyProfileResponse:
    # Set all existing to not current
    await db.execute(
        update(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)
        .values(is_current=False)
    )

    company_name = profile_data.get("companyName", "")
    cp = CompanyProfile(
        user_id=user_id,
        company_name=company_name,
        profile_data=profile_data,
        profile_markdown=profile_data.get("markdown", ""),
        is_current=True,
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return _profile_data_to_response(cp)


async def update_profile(
    db: AsyncSession, profile_id: int, profile_data: dict
) -> CompanyProfileResponse | None:
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.id == profile_id)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        return None

    company_name = profile_data.get("companyName", "")
    cp.company_name = company_name
    cp.profile_data = profile_data
    cp.profile_markdown = profile_data.get("markdown", cp.profile_markdown)

    await db.commit()
    await db.refresh(cp)
    return _profile_data_to_response(cp)
