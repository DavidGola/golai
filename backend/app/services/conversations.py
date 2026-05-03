import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message, MessageRole
from app.schemas.conversation import ConversationCreate, ConversationUpdate


async def list_conversations(db: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_conversation(
    db: AsyncSession, user_id: uuid.UUID, payload: ConversationCreate
) -> Conversation:
    conv = Conversation(user_id=user_id, title=payload.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation_with_messages(
    db: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID
) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.messages.sort(key=lambda m: m.created_at)
    return conv


async def rename_conversation(
    db: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID, payload: ConversationUpdate
) -> Conversation | None:
    conv = await db.get(Conversation, conv_id)
    if not conv or conv.user_id != user_id:
        return None
    conv.title = payload.title
    await db.commit()
    await db.refresh(conv)
    return conv


async def delete_conversation(
    db: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID
) -> bool:
    conv = await db.get(Conversation, conv_id)
    if not conv or conv.user_id != user_id:
        return False
    await db.delete(conv)
    await db.commit()
    return True


async def append_message(
    db: AsyncSession,
    conv_id: uuid.UUID,
    role: MessageRole,
    content: str,
    tokens_used: int | None = None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv_id,
        role=role,
        content=content,
        tokens_used=tokens_used,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
