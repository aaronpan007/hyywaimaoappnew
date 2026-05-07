from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DBSession
from app.schemas.conversation import ConversationListItem, ConversationMessageResponse
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
