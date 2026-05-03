from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from app.ai import agent as agent_module
from app.config import settings


def test_build_model_uses_anthropic_with_cache_settings(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "anthropic/claude-sonnet-4-5")
    monkeypatch.setattr(settings, "anthropic_api_key", "anthropic-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, AnthropicModel)
    assert model.model_name == "claude-sonnet-4-5"
    assert model_settings == {
        "anthropic_cache_instructions": True,
        "anthropic_cache_tool_definitions": True,
    }


def test_build_model_uses_openai_api_key(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "openai/gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_api_key", "openai-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "gpt-4o-mini"
    assert model.client.api_key == "openai-test-key"
    assert model_settings is None


def test_build_model_uses_gemini_api_key(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "gemini/gemini-2.5-flash")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, GoogleModel)
    assert model.model_name == "gemini-2.5-flash"
    assert model.model_id == "google-gla:gemini-2.5-flash"
    assert model_settings is None


def test_build_model_uses_openrouter_api_key(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "openrouter/qwen/qwen3-next-80b-a3b-instruct:free")
    monkeypatch.setattr(settings, "litellm_api_base", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "openrouter-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "qwen/qwen3-next-80b-a3b-instruct:free"
    assert model.model_id == "litellm:qwen/qwen3-next-80b-a3b-instruct:free"
    assert str(model.client.base_url) == "https://openrouter.ai/api/v1/"
    assert model.client.api_key == "openrouter-test-key"
    assert model_settings is None


def test_build_model_uses_glm_api_key(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "zai/glm-5.1")
    monkeypatch.setattr(settings, "litellm_api_base", "")
    monkeypatch.setattr(settings, "glm_api_key", "glm-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "glm-5.1"
    assert model.model_id == "litellm:glm-5.1"
    assert str(model.client.base_url) == "https://api.z.ai/api/paas/v4/"
    assert model.client.api_key == "glm-test-key"
    assert model_settings is None


def test_build_model_falls_back_to_litellm_without_wrong_provider_key(monkeypatch):
    monkeypatch.setattr(settings, "litellm_model", "mistral/mistral-large-latest")
    monkeypatch.setattr(settings, "litellm_api_base", "http://litellm.test")
    monkeypatch.setattr(settings, "anthropic_api_key", "anthropic-test-key")
    monkeypatch.setattr(settings, "openai_api_key", "openai-test-key")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test-key")
    monkeypatch.setattr(settings, "openrouter_api_key", "openrouter-test-key")
    monkeypatch.setattr(settings, "glm_api_key", "glm-test-key")

    model, model_settings = agent_module._build_model()

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "mistral/mistral-large-latest"
    assert model.model_id == "litellm:mistral/mistral-large-latest"
    assert model.client.api_key == "litellm-placeholder"
    assert model_settings is None
