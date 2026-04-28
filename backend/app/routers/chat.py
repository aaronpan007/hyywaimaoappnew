from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, DBSession
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest, db: DBSession, user_id: CurrentUser):
    try:
        result = await chat_service.start_chat(req.message, db, user_id)
    except chat_service.ConfigRequiredError as e:
        return StreamingResponse(
            chat_service.config_error_stream(e.missing),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    if result["type"] == "chat":
        return StreamingResponse(
            chat_service.chat_reply_stream(result["reply"]),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    if result["type"] == "confirm":
        return StreamingResponse(
            chat_service.confirm_params_stream(result["params"], result["reply"]),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    # type == "pipeline"
    return StreamingResponse(
        chat_service.stream_task_progress(result["task_id"], db),
        media_type="text/event-stream",
        headers=chat_service.SSE_HEADERS,
    )
