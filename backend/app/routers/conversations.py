from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DBSession
from app.schemas.conversation import (
    ConversationListItem,
    ConversationMessageResponse,
    UpdateConversationRequest,
)
from app.services import conversation_service

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationListItem])
async def list_conversations(db: DBSession, user_id: CurrentUser):
    return await conversation_service.get_conversations(db, user_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
async def get_conversation_messages(
    conversation_id: int, db: DBSession, user_id: CurrentUser,
):
    messages = await conversation_service.get_messages(db, conversation_id, user_id)
    if not messages:
        # Check if conversation exists at all
        from app.models.conversation import Conversation
        conv = await db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user_id:
            raise HTTPException(404, "Conversation not found")
    return messages


@router.patch("/conversations/{conversation_id}", response_model=ConversationListItem)
async def update_conversation(
    conversation_id: int,
    req: UpdateConversationRequest,
    db: DBSession,
    user_id: CurrentUser,
):
    conv = await conversation_service.update_conversation_title(
        db,
        conversation_id,
        user_id,
        req.title,
    )
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return {
        "id": conv.id,
        "title": conv.title,
        "mode": conv.mode,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "message_count": 0,
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: DBSession, user_id: CurrentUser):
    deleted = await conversation_service.delete_conversation(db, conversation_id, user_id)
    if not deleted:
        raise HTTPException(404, "Conversation not found")
    return {"deleted": True}
