from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.conversation import Message, MessageRole
from app.schemas.conversation import ConversationUpdate
from app.services.conversations import (
    append_message,
    delete_conversation,
    get_conversation_with_messages,
    rename_conversation,
)


async def test_get_conversation_wrong_owner_returns_none(db_session, user_b, conversation_a):
    result = await get_conversation_with_messages(db_session, user_b.id, conversation_a.id)
    assert result is None


async def test_get_conversation_messages_sorted_asc(db_session, user_a, conversation_a):
    now = datetime.utcnow()
    for i, content in enumerate(["first", "second", "third"]):
        msg = Message(
            conversation_id=conversation_a.id,
            role=MessageRole.user,
            content=content,
            created_at=now + timedelta(seconds=i),
        )
        db_session.add(msg)
    await db_session.commit()

    conv = await get_conversation_with_messages(db_session, user_a.id, conversation_a.id)
    assert conv is not None
    assert [m.content for m in conv.messages] == ["first", "second", "third"]


async def test_delete_conversation_cascades_messages(db_session, user_a, conversation_a):
    await append_message(db_session, conversation_a.id, MessageRole.user, "hello")

    deleted = await delete_conversation(db_session, user_a.id, conversation_a.id)
    assert deleted is True

    msgs = (await db_session.execute(
        select(Message).where(Message.conversation_id == conversation_a.id)
    )).scalars().all()
    assert msgs == []


async def test_rename_conversation_wrong_owner_returns_none(db_session, user_a, user_b, conversation_a):
    result = await rename_conversation(
        db_session, user_b.id, conversation_a.id, ConversationUpdate(title="hacked")
    )
    assert result is None

    conv = await get_conversation_with_messages(db_session, user_a.id, conversation_a.id)
    assert conv is not None
    assert conv.title == "Test conv"
