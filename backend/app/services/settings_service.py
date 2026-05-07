from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_profile import CompanyProfile
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    EmailSettingsResponse,
    UpdateSettingsRequest,
)
from app.config import settings
from app.utils.prefix_generator import generate_prefixes


def _normalize_mail_domain(domain: str) -> str:
    return (domain or "").strip().lstrip("@")


def _recommended_sender_name(company_name: str) -> str:
    import re

    name = (company_name or "").strip()
    if not name:
        return ""

    tokens = re.findall(r"[A-Za-z0-9]+", name)
    for token in tokens:
        if len(token) >= 2 and token.upper() == token:
            return token

    legal_words = {
        "co", "company", "limited", "ltd", "inc", "corp", "corporation",
        "group", "technology", "technologies", "building", "material",
        "materials", "industrial", "industry",
    }
    for token in tokens:
        if token.lower() not in legal_words:
            return token

    return tokens[0] if tokens else name.split()[0]


async def _get_current_profile_for_settings(
    db: AsyncSession, user_id: int
) -> CompanyProfile | None:
    result = await db.execute(
        select(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)  # noqa: E712
        .order_by(CompanyProfile.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_recommended_email_settings(
    db: AsyncSession,
    user_id: int,
    profile_id: int | None,
    profile_data: dict | None,
) -> UserSettings:
    """Create a default email config from the current company profile.

    Settings tied to another profile are treated as stale recommendations and
    refreshed. Settings already tied to the current profile preserve user edits.
    """
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    us = result.scalar_one_or_none()
    if us is None:
        us = UserSettings(user_id=user_id)
        db.add(us)
        await db.flush()

    profile = profile_data if isinstance(profile_data, dict) else {}
    company_name = (
        profile.get("company_name")
        or profile.get("companyName")
        or ""
    )
    should_refresh_profile_defaults = (
        profile_id is not None and us.profile_id != profile_id
    )
    if should_refresh_profile_defaults or not (us.sender_name or "").strip():
        us.sender_name = _recommended_sender_name(company_name)
    if should_refresh_profile_defaults or not (us.from_email_prefix or "").strip():
        us.from_email_prefix = "sales"
    if should_refresh_profile_defaults:
        us.reply_to_email = ""
        us.confirmed_at = None
    if profile_id is not None:
        us.profile_id = profile_id

    await db.commit()
    await db.refresh(us)
    return us


async def get_settings(db: AsyncSession, user_id: int) -> EmailSettingsResponse:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()
    current_profile: CompanyProfile | None = None

    if us is None:
        current_profile = await _get_current_profile_for_settings(db, user_id)
        if current_profile is not None:
            us = await ensure_recommended_email_settings(
                db,
                user_id,
                current_profile.id,
                current_profile.profile_data if isinstance(current_profile.profile_data, dict) else {},
            )
        else:
            return EmailSettingsResponse(
                sender_name="",
                reply_to_email="",
                from_email_prefix="",
                mail_domain=_normalize_mail_domain(settings.mail_domain),
            )

    if current_profile is None:
        current_profile = await _get_current_profile_for_settings(db, user_id)

    if (
        current_profile is not None
        and (
            us.profile_id != current_profile.id
            or not (us.sender_name or "").strip()
            or not (us.from_email_prefix or "").strip()
        )
    ):
        us = await ensure_recommended_email_settings(
            db,
            user_id,
            current_profile.id,
            current_profile.profile_data if isinstance(current_profile.profile_data, dict) else {},
        )

    if us is None:
        return EmailSettingsResponse(
            sender_name="",
            reply_to_email="",
            from_email_prefix="",
            mail_domain=_normalize_mail_domain(settings.mail_domain),
        )

    return EmailSettingsResponse(
        sender_name=us.sender_name,
        reply_to_email=us.reply_to_email,
        from_email_prefix=us.from_email_prefix,
        mail_domain=_normalize_mail_domain(settings.mail_domain),
        configured_at=str(us.confirmed_at) if us.confirmed_at else None,
    )


async def update_settings(
    db: AsyncSession, user_id: int, req: UpdateSettingsRequest
) -> EmailSettingsResponse:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()

    if us is None:
        us = UserSettings(user_id=user_id)
        db.add(us)
        await db.flush()

    if req.sender_name is not None:
        us.sender_name = req.sender_name
    if req.reply_to_email is not None:
        us.reply_to_email = req.reply_to_email.strip()
    if req.from_email_prefix is not None:
        us.from_email_prefix = req.from_email_prefix.strip().strip("@").split("@", 1)[0]
    us.confirmed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(us)

    return await get_settings(db, user_id)


def generate_prefix(company_name: str) -> list[str]:
    return generate_prefixes(company_name)
