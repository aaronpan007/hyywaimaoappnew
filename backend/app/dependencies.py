import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Annotated, AsyncGenerator
from urllib.parse import unquote

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.auth import AuthSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


def _verify_signed_cookie(value: str, secret: str) -> str | None:
    decoded = unquote(value or "")
    if "." not in decoded:
        return None
    token, signature = decoded.rsplit(".", 1)
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    if hmac.compare_digest(expected, signature):
        return token
    return None


def _get_session_cookie(request: Request) -> str:
    for name in (
        "better-auth.session_token",
        "__Secure-better-auth.session_token",
        "better-auth-session_token",
        "__Secure-better-auth-session_token",
    ):
        value = request.cookies.get(name)
        if value:
            return value
    return ""


async def get_current_user(request: Request, db: DBSession) -> int:
    if not settings.better_auth_secret:
        raise HTTPException(status_code=500, detail="BETTER_AUTH_SECRET is not configured")

    cookie_value = _get_session_cookie(request)
    token = _verify_signed_cookie(cookie_value, settings.better_auth_secret)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await db.execute(select(AuthSession).where(AuthSession.token == token))
    session = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if session is None or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Session expired")

    return session.user_id


CurrentUser = Annotated[int, Depends(get_current_user)]
