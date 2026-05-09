from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser, DBSession
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest, db: DBSession, user_id: CurrentUser):
    # Pass files to start_chat as part of intent params
    files_data = None
    if req.files:
        files_data = [{"filename": f.filename, "data": f.data} for f in req.files]

    try:
        result = await chat_service.start_chat(
            req.message, db, user_id, images=req.images, files=files_data,
            conversation_id=req.conversation_id, mode=req.mode,
        )
    except chat_service.ConfigRequiredError as e:
        return StreamingResponse(
            chat_service.config_error_stream(e.missing, req.conversation_id),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    conv_id = result.get("conversation_id")

    if result["type"] == "chat":
        return StreamingResponse(
            chat_service.chat_reply_stream(result["reply"], conversation_id=conv_id, db=db),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    if result["type"] == "callout":
        return StreamingResponse(
            chat_service.callout_reply_stream(result["callout"], conversation_id=conv_id, db=db),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    if result["type"] == "email_settings_prompt":
        return StreamingResponse(
            chat_service.email_settings_prompt_stream(
                result["reply"],
                result["state"],
                conversation_id=conv_id,
                db=db,
            ),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    if result["type"] == "confirm":
        # Dispatch by confirm type
        params = result.get("params", {})
        confirm_type = params.get("confirm_type", "customer_acquisition")
        if confirm_type == "email_craft":
            return StreamingResponse(
                chat_service.confirm_email_craft_stream(params, result["reply"], conversation_id=conv_id),
                media_type="text/event-stream",
                headers=chat_service.SSE_HEADERS,
            )
        return StreamingResponse(
            chat_service.confirm_params_stream(params, result["reply"], conversation_id=conv_id),
            media_type="text/event-stream",
            headers=chat_service.SSE_HEADERS,
        )

    # type == "pipeline"
    return StreamingResponse(
        chat_service.stream_task_progress(result["task_id"], db, conversation_id=conv_id),
        media_type="text/event-stream",
        headers=chat_service.SSE_HEADERS,
    )
