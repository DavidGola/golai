import json
from typing import AsyncIterator

from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    PartDeltaEvent,
    PartStartEvent,
)
from pydantic_ai.messages import TextPart, TextPartDelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import AnonymousAgentDeps, anonymous_agent, history_dicts_to_messages
from app.ai.citations import cited_games_sse_event
from app.config import settings
from app.observability import captured_input, observe, safe_update
from app.schemas.chat import AnonymousHistoryMessage


async def stream_anonymous_reply(
    db: AsyncSession,
    content: str,
    history: list[AnonymousHistoryMessage],
) -> AsyncIterator[str]:
    history_dicts = [{"role": m.role, "content": m.content} for m in history]
    message_history = history_dicts_to_messages(history_dicts)
    deps = AnonymousAgentDeps(db=db)

    usage_info = None
    final_output = ""

    metadata = {"model": settings.litellm_model, "route": "anonymous"}

    with observe(
        "chat.stream_anonymous_reply",
        input=captured_input(content),
        metadata=metadata,
        tags=["chat", "anonymous"],
    ) as observation:
        try:
            async for event in anonymous_agent.run_stream_events(
                content,
                message_history=message_history,
                deps=deps,
            ):
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    if event.part.content:
                        yield f"event: token\ndata: {json.dumps({'text': event.part.content})}\n\n"
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    if event.delta.content_delta:
                        yield f"event: token\ndata: {json.dumps({'text': event.delta.content_delta})}\n\n"
                elif isinstance(event, FunctionToolCallEvent):
                    yield f"event: tool\ndata: {json.dumps({'name': event.part.tool_name})}\n\n"
                elif isinstance(event, AgentRunResultEvent):
                    final_output = event.result.output
                    usage = event.result.usage()
                    usage_info = {
                        "total_tokens": usage.total_tokens or 0,
                        "input_tokens": usage.input_tokens or 0,
                        "output_tokens": usage.output_tokens or 0,
                        "cache_read_tokens": usage.cache_read_tokens or 0,
                        "cache_write_tokens": usage.cache_write_tokens or 0,
                    }
        except Exception as e:
            safe_update(
                observation,
                output={"error": str(e)},
                metadata={**metadata, "status": "error"},
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            return

        safe_update(
            observation,
            output=captured_input(final_output),
            metadata={**metadata, "status": "success", **(usage_info or {})},
        )

    if final_output:
        cited_sse, _ = await cited_games_sse_event(db, final_output)
        if cited_sse:
            yield cited_sse

    yield f"event: done\ndata: {json.dumps({'tokens_used': usage_info.get('total_tokens') if usage_info else None})}\n\n"
