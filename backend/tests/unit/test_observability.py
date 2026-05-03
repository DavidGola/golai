import sys
from types import SimpleNamespace

from app import observability
from app.config import settings


def test_agent_instrumentation_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_enabled", False)

    assert observability.get_agent_instrumentation() is None


def test_agent_instrumentation_uses_content_flag(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_enabled", True)
    monkeypatch.setattr(settings, "langfuse_capture_content", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(observability, "initialize_langfuse", lambda: None)

    instrumentation = observability.get_agent_instrumentation()

    assert instrumentation is not None
    assert instrumentation.include_content is True


def test_captured_input_respects_content_flag(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_capture_content", True)
    assert observability.captured_input("prompt") == "prompt"

    monkeypatch.setattr(settings, "langfuse_capture_content", False)
    assert observability.captured_input("prompt") is None


def test_sentry_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "sentry_enabled", False)
    monkeypatch.setattr(observability, "_sentry_initialized", False)

    observability.initialize_sentry()

    assert observability.sentry_ready() is False


def test_sentry_initializes_when_configured(monkeypatch):
    calls = []

    fake_sentry_sdk = SimpleNamespace(init=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry_sdk)
    monkeypatch.setattr(observability, "_sentry_initialized", False)
    monkeypatch.setattr(settings, "sentry_enabled", True)
    monkeypatch.setattr(settings, "sentry_dsn", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setattr(settings, "sentry_environment", "test")
    monkeypatch.setattr(settings, "sentry_release", "golai@test")
    monkeypatch.setattr(settings, "sentry_traces_sample_rate", 0.0)

    observability.initialize_sentry()

    assert calls == [
        {
            "dsn": "https://public@example.ingest.sentry.io/1",
            "environment": "test",
            "release": "golai@test",
            "send_default_pii": False,
            "traces_sample_rate": 0.0,
        }
    ]
