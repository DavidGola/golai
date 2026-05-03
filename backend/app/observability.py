import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

from pydantic_ai.models.instrumented import InstrumentationSettings

from app.config import settings

logger = logging.getLogger(__name__)

_langfuse_client: Any | None = None
_langfuse_initialized = False
_sentry_initialized = False


class _NoopObservation:
    def update(self, **kwargs: Any) -> None:
        pass

    def update_trace(self, **kwargs: Any) -> None:
        pass


def _credentials_configured() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def langfuse_ready() -> bool:
    return settings.langfuse_enabled and _credentials_configured()


def sentry_ready() -> bool:
    return settings.sentry_enabled and bool(settings.sentry_dsn)


def initialize_sentry() -> None:
    global _sentry_initialized

    if _sentry_initialized:
        return

    _sentry_initialized = True

    if not settings.sentry_enabled:
        return

    if not settings.sentry_dsn:
        logger.warning("Sentry enabled but SENTRY_DSN is missing")
        return

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("Sentry enabled but the sentry-sdk package is not installed")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=settings.sentry_release or None,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    logger.info("Sentry error monitoring enabled")


def initialize_langfuse() -> Any | None:
    global _langfuse_client, _langfuse_initialized

    if _langfuse_initialized:
        return _langfuse_client

    _langfuse_initialized = True

    if not settings.langfuse_enabled:
        return None

    if not _credentials_configured():
        logger.warning("Langfuse enabled but LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY is missing")
        return None

    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_BASE_URL"] = settings.langfuse_base_url

    try:
        from langfuse import get_client
    except ImportError:
        logger.warning("Langfuse enabled but the langfuse package is not installed")
        return None

    _langfuse_client = get_client()
    logger.info("Langfuse observability enabled")
    return _langfuse_client


def get_agent_instrumentation() -> InstrumentationSettings | None:
    if not settings.langfuse_enabled:
        return None

    initialize_langfuse()
    return InstrumentationSettings(include_content=settings.langfuse_capture_content)


def captured_input(value: Any) -> Any | None:
    return value if settings.langfuse_capture_content else None


def safe_update(observation: Any, **kwargs: Any) -> None:
    update = getattr(observation, "update", None)
    if update is None:
        return

    try:
        update(**kwargs)
    except Exception:
        logger.debug("Failed to update Langfuse observation", exc_info=True)


def safe_update_trace(observation: Any, **kwargs: Any) -> None:
    update_trace = getattr(observation, "update_trace", None)
    if update_trace is None:
        return

    try:
        update_trace(**kwargs)
    except Exception:
        logger.debug("Failed to update Langfuse trace", exc_info=True)


@contextmanager
def observe(
    name: str,
    *,
    as_type: str = "span",
    input: Any | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any]:
    client = initialize_langfuse()
    if client is None:
        yield _NoopObservation()
        return

    with client.start_as_current_observation(name=name, as_type=as_type, input=input, metadata=metadata) as observation:
        try:
            from langfuse import propagate_attributes
        except ImportError:
            propagate_attributes = None

        trace_kwargs: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata,
            "tags": tags,
        }
        trace_kwargs = {key: value for key, value in trace_kwargs.items() if value}
        if trace_kwargs:
            safe_update_trace(observation, **trace_kwargs)

        if propagate_attributes is None:
            yield observation
            return

        with propagate_attributes(**trace_kwargs):
            yield observation


def flush_langfuse() -> None:
    if _langfuse_client is None:
        return

    flush = getattr(_langfuse_client, "flush", None)
    if flush is None:
        return

    try:
        flush()
    except Exception:
        logger.debug("Failed to flush Langfuse events", exc_info=True)
