from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.chat import AnonymousMessageCreate
from app.services.anonymous_chat import stream_anonymous_reply
from app.services.rate_limits import RateLimitExceeded, check_chat_rate_limit

router = APIRouter(prefix="/chat", tags=["anonymous_chat"])


@router.post("/anonymous")
async def anonymous_chat(
    payload: AnonymousMessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if settings.chat_rate_limit_enabled:
        client_ip = request.client.host if request.client else "unknown"
        try:
            await check_chat_rate_limit(
                db,
                bucket_key=f"chat:anonymous:{client_ip}",
                scope="chat:anonymous",
                limit=settings.chat_anonymous_rate_limit_per_hour,
            )
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de messages. Réessaie plus tard.",
                headers={"Retry-After": str(exc.retry_after)},
            ) from exc

    return StreamingResponse(
        stream_anonymous_reply(db, payload.content, payload.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
