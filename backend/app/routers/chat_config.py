from fastapi import APIRouter

from app.config import settings
from app.schemas.chat import ChatConfigRead

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/config", response_model=ChatConfigRead)
async def get_chat_config():
    return ChatConfigRead(model=settings.litellm_model)
