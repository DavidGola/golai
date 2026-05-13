import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_active_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
    MessageCreate,
)
from app.services import conversations as conv_service
from app.services.chat import stream_reply
from app.services.rate_limits import RateLimitExceeded, check_chat_rate_limit

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    return await conv_service.list_conversations(db, current_user.id)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    return await conv_service.create_conversation(db, current_user.id, payload)


@router.get("/{conv_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    conv = await conv_service.get_conversation_with_messages(db, current_user.id, conv_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")
    return conv


@router.patch("/{conv_id}", response_model=ConversationRead)
async def rename_conversation(
    conv_id: uuid.UUID,
    payload: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    conv = await conv_service.rename_conversation(db, current_user.id, conv_id, payload)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")
    return conv


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    deleted = await conv_service.delete_conversation(db, current_user.id, conv_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")


@router.post("/{conv_id}/messages")
async def send_message(
    conv_id: uuid.UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    conv = await conv_service.get_conversation_with_messages(db, current_user.id, conv_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")

    if settings.chat_rate_limit_enabled:
        try:
            await check_chat_rate_limit(
                db,
                bucket_key=f"chat:auth:{current_user.id}",
                scope="chat:auth",
                limit=settings.chat_auth_rate_limit_per_hour,
            )
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de messages. Réessaie plus tard.",
                headers={"Retry-After": str(exc.retry_after)},
            ) from exc

    return StreamingResponse(
        stream_reply(db, current_user, conv, payload.content, intent=payload.intent),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
