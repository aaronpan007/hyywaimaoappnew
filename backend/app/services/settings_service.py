from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import UserSettings
from app.schemas.settings import (
    EmailSettingsResponse,
    UpdateSettingsRequest,
)
from app.config import settings
from app.utils.prefix_generator import generate_prefixes


async def get_settings(db: AsyncSession, user_id: int) -> EmailSettingsResponse:
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    us = result.scalar_one_or_none()

    if us is None:
        return EmailSettingsResponse(
            sender_name="",
            reply_to_email="",
            from_email_prefix="",
            mail_domain=settings.mail_domain,
        )

    return EmailSettingsResponse(
        sender_name=us.sender_name,
        reply_to_email=us.reply_to_email,
        from_email_prefix=us.from_email_prefix,
        mail_domain=settings.mail_domain,
        configured_at=str(us.updated_at) if us.updated_at else None,
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
        us.reply_to_email = req.reply_to_email
    if req.from_email_prefix is not None:
        us.from_email_prefix = req.from_email_prefix

    await db.commit()
    await db.refresh(us)

    return await get_settings(db, user_id)


def generate_prefix(company_name: str) -> list[str]:
    return generate_prefixes(company_name)
