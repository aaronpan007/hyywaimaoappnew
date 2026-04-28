from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


# Phase 1: stub — always returns user_id=1
async def get_current_user() -> int:
    return 1


CurrentUser = Annotated[int, Depends(get_current_user)]
