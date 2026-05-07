"""Conversation CRUD: persist chat history to PostgreSQL."""

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.models.conversation import Conversation, ConversationMessage


async def get_conversations(db, user_id: int) -> list[dict]:
    """Return conversations ordered by updated_at DESC with message counts."""
    rows = await db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.mode,
            Conversation.created_at,
            Conversation.updated_at,
            func.count(ConversationMessage.id).label("message_count"),
        )
        .outerjoin(ConversationMessage, ConversationMessage.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc().nullslast())
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "mode": r.mode,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "message_count": r.message_count,
        }
        for r in rows.all()
    ]


async def get_messages(db, conversation_id: int, user_id: int) -> list[ConversationMessage]:
    """Return all messages for a conversation, ordered by sort_order ASC."""
    # Verify ownership
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        return []

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.sort_order.asc())
    )
    return list(result.scalars().all())


async def create_conversation(
    db, user_id: int, title: str, mode: str = "general",
) -> Conversation:
    """Create a new conversation and return it."""
    conv = Conversation(user_id=user_id, title=title, mode=mode)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def save_message(
    db,
    conversation_id: int,
    role: str,
    content: str,
    message_type: str = "text",
    extra_data: dict | None = None,
) -> ConversationMessage:
    """Append a message to a conversation. Auto-increments sort_order."""
    # Get next sort_order
    result = await db.execute(
        select(func.coalesce(func.max(ConversationMessage.sort_order), 0))
        .where(ConversationMessage.conversation_id == conversation_id)
    )
    next_order = result.scalar() + 1

    msg = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_type=message_type,
        extra_data=extra_data,
        sort_order=next_order,
    )
    db.add(msg)

    # Touch conversation updated_at
    conv = await db.get(Conversation, conversation_id)
    if conv is not None:
        conv.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(msg)
    return msg
