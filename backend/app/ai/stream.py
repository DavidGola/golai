import json
import logging
import re
import time
from typing import AsyncIterator

from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
)
from pydantic_ai.messages import TextPart, TextPartDelta, ToolReturnPart

from app.ai.agent import AgentDeps, agent, db_messages_to_history

logger = logging.getLogger(__name__)

_PRE_TOOL_BUFFER_THRESHOLD = 50

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_UUID_LEN = 36


class _UuidStripper:
    """
    Filtre les UUIDs dans un flux de chunks.

    Stratégie : applique le regex sur le buffer complet d'abord (retire les UUIDs complets),
    puis émet tout sauf les 35 derniers chars (lookahead pour les UUIDs en cours d'arrivée).
    Les 35 derniers chars constituent un préfixe potentiel de UUID max non encore complet.
    """
    _LOOKAHEAD = _UUID_LEN - 1  # 35

    def __init__(self) -> None:
        self.buf = ""

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        clean = _UUID_RE.sub("", self.buf)
        if len(clean) > self._LOOKAHEAD:
            emit = clean[:-self._LOOKAHEAD]
            self.buf = clean[-self._LOOKAHEAD:]
            return emit
        self.buf = clean
        return ""

    def flush(self) -> str:
        out = _UUID_RE.sub("", self.buf)
        self.buf = ""
        return out


def _safe_json_preview(value: object, limit: int = 400) -> str:
    try:
        raw = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        raw = str(value)
    return raw[:limit] + "…" if len(raw) > limit else raw


def _safe_json(value: object) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return str(value)


def _extract_text_from_part_start(event: PartStartEvent) -> str:
    if isinstance(event.part, TextPart) and event.part.content:
        return event.part.content
    return ""


def _extract_text_from_part_delta(event: PartDeltaEvent) -> str:
    if isinstance(event.delta, TextPartDelta) and event.delta.content_delta:
        return event.delta.content_delta
    return ""


async def stream_agent(
    deps: AgentDeps,
    user_message: str,
    history: list,
) -> AsyncIterator[dict]:
    """
    Génère des events normalisés depuis le stream pydantic-ai.

    Events émis :
    - {"event": "token", "data": <chunk de texte>}
    - {"event": "tool", "data": <nom de l'outil>}
    - {"event": "tool_call", "data": {tool_call_id, name, args_preview}}
    - {"event": "tool_result", "data": {tool_call_id, name, duration_ms, result_preview}}
    - {"event": "proposal", "data": <payload de la proposition>}
    - {"event": "result", "data": {"output": <str>, "usage": {...}}}
    - {"event": "error", "data": <str>}
    """
    message_history = db_messages_to_history(history)

    pre_tool_buffer: list[str] = []
    tool_called = False
    buffer_flushed = False
    stripper = _UuidStripper()
    tool_call_starts: dict[str, float] = {}

    async def _flush_buffer():
        nonlocal buffer_flushed
        for chunk in pre_tool_buffer:
            filtered = stripper.feed(chunk)
            if filtered:
                yield {"event": "token", "data": filtered}
        pre_tool_buffer.clear()
        buffer_flushed = True

    try:
        async for event in agent.run_stream_events(
            user_message,
            message_history=message_history,
            deps=deps,
        ):
            if isinstance(event, PartStartEvent):
                text = _extract_text_from_part_start(event)
                if not text:
                    continue
                if tool_called or buffer_flushed:
                    filtered = stripper.feed(text)
                    if filtered:
                        yield {"event": "token", "data": filtered}
                else:
                    pre_tool_buffer.append(text)
                    if sum(len(c) for c in pre_tool_buffer) >= _PRE_TOOL_BUFFER_THRESHOLD:
                        async for e in _flush_buffer():
                            yield e

            elif isinstance(event, PartDeltaEvent):
                text = _extract_text_from_part_delta(event)
                if not text:
                    continue
                if tool_called or buffer_flushed:
                    filtered = stripper.feed(text)
                    if filtered:
                        yield {"event": "token", "data": filtered}
                else:
                    pre_tool_buffer.append(text)
                    if sum(len(c) for c in pre_tool_buffer) >= _PRE_TOOL_BUFFER_THRESHOLD:
                        async for e in _flush_buffer():
                            yield e

            elif isinstance(event, FunctionToolCallEvent):
                if not buffer_flushed:
                    pre_tool_buffer.clear()
                tool_called = True
                args_preview = _safe_json_preview(event.part.args)
                tool_call_starts[event.part.tool_call_id] = time.monotonic()
                logger.info("agent.tool_call", extra={
                    "tool_name": event.part.tool_name,
                    "tool_call_id": event.part.tool_call_id,
                    "args_preview": args_preview,
                })
                yield {"event": "tool", "data": event.part.tool_name}
                yield {"event": "tool_call", "data": {
                    "tool_call_id": event.part.tool_call_id,
                    "name": event.part.tool_name,
                    "args_preview": args_preview,
                }}

            elif isinstance(event, FunctionToolResultEvent):
                started = tool_call_starts.pop(event.tool_call_id, None)
                duration_ms = round((time.monotonic() - started) * 1000) if started is not None else None
                result_content = getattr(event.result, "content", None)
                result_preview = _safe_json_preview(result_content)
                result_json = _safe_json(result_content)
                logger.info("agent.tool_result", extra={
                    "tool_name": getattr(event.result, "tool_name", None),
                    "tool_call_id": event.tool_call_id,
                    "duration_ms": duration_ms,
                    "result_preview": result_preview,
                })
                yield {"event": "tool_result", "data": {
                    "tool_call_id": event.tool_call_id,
                    "name": getattr(event.result, "tool_name", None),
                    "duration_ms": duration_ms,
                    "result_preview": result_preview,
                    "result_json": result_json,
                }}
                if (
                    isinstance(event.result, ToolReturnPart)
                    and event.result.tool_name.startswith("propose_")
                    and isinstance(event.result.content, dict)
                    and "action_type" in event.result.content
                    and "error" not in event.result.content
                ):
                    # Draft validé par le tool — sera persisté en fin de stream
                    # par chat.py (qui émettra le vrai event 'proposal' avec l'id DB).
                    yield {"event": "draft", "data": event.result.content}

            elif isinstance(event, AgentRunResultEvent):
                if not tool_called and not buffer_flushed:
                    async for e in _flush_buffer():
                        yield e
                tail = stripper.flush()
                if tail:
                    yield {"event": "token", "data": tail}
                usage = event.result.usage()
                clean_output = _UUID_RE.sub("", event.result.output)
                yield {
                    "event": "result",
                    "data": {
                        "output": clean_output,
                        "usage": {
                            "total_tokens": usage.total_tokens or 0,
                            "input_tokens": usage.input_tokens or 0,
                            "output_tokens": usage.output_tokens or 0,
                            "cache_read_tokens": usage.cache_read_tokens or 0,
                            "cache_write_tokens": usage.cache_write_tokens or 0,
                        },
                    },
                }
    except Exception as e:
        yield {"event": "error", "data": str(e)}
