from typing import AsyncIterator

from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
)
from pydantic_ai.messages import TextPart, TextPartDelta

from app.ai.agent import AgentDeps, agent, db_messages_to_history

_PRE_TOOL_BUFFER_THRESHOLD = 50


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

    Les tokens émis avant un appel d'outil sont bufférisés et silencieusement
    ignorés si un tool call survient, ce qui évite le "texte qui disparaît".
    Si aucun tool n'est appelé et que le buffer dépasse le seuil, il est flushé.

    Events émis :
    - {"event": "token", "data": <chunk de texte>}
    - {"event": "tool", "data": <nom de l'outil>}
    - {"event": "result", "data": {"output": <str>, "usage": {...}}}
    - {"event": "error", "data": <str>}
    """
    message_history = db_messages_to_history(history)

    pre_tool_buffer: list[str] = []
    tool_called = False
    buffer_flushed = False

    async def _flush_buffer():
        nonlocal buffer_flushed
        for chunk in pre_tool_buffer:
            yield {"event": "token", "data": chunk}
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
                    yield {"event": "token", "data": text}
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
                    yield {"event": "token", "data": text}
                else:
                    pre_tool_buffer.append(text)
                    if sum(len(c) for c in pre_tool_buffer) >= _PRE_TOOL_BUFFER_THRESHOLD:
                        async for e in _flush_buffer():
                            yield e

            elif isinstance(event, FunctionToolCallEvent):
                if not buffer_flushed:
                    pre_tool_buffer.clear()
                tool_called = True
                yield {"event": "tool", "data": event.part.tool_name}

            elif isinstance(event, FunctionToolResultEvent):
                pass

            elif isinstance(event, AgentRunResultEvent):
                if not tool_called and not buffer_flushed:
                    async for e in _flush_buffer():
                        yield e
                usage = event.result.usage()
                yield {
                    "event": "result",
                    "data": {
                        "output": event.result.output,
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
