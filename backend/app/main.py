from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import async_session_factory
from app.routers import chat, settings as settings_router, tasks, leads, profile, emails
from app.services import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: clean up zombie tasks from previous run
    async with async_session_factory() as db:
        await task_manager.cleanup_on_startup(db)
    yield


app = FastAPI(
    title="AI外贸业务员 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(emails.router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
