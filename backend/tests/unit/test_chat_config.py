from app.config import settings
from app.routers.chat_config import get_chat_config


async def test_get_chat_config_returns_active_model(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "test/provider-model")

    config = await get_chat_config()

    assert config.model == "test/provider-model"
