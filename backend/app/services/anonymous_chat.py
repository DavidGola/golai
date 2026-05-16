import json
import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import AnonymousAgentDeps, anonymous_agent
from app.ai.citations import cited_games_sse_event
from app.ai.stream import format_sse_event, stream_agent
from app.config import settings
from app.observability import captured_input, observe, safe_update
from app.schemas.chat import AnonymousHistoryMessage

logger = logging.getLogger(__name__)


async def stream_anonymous_reply(
    db: AsyncSession,
    content: str,
    history: list[AnonymousHistoryMessage],
) -> AsyncIterator[str]:
    """Stream SSE pour le chat anonyme. Pas de persistance, pas de Proposals.

    Mêmes events SSE que stream_reply (auth) sauf 'proposal' qui ne peut pas
    être émis (l'agent anonyme n'a aucun tool propose_*, garanti par toolset
    isolation — cf. test_anonymous_agent_safety).
    """
    history_dicts = [{"role": m.role, "content": m.content} for m in history]
    deps = AnonymousAgentDeps(db=db)

    metadata = {"model": settings.litellm_model, "route": "anonymous"}
    final_output = ""
    usage_info: dict | None = None

    with observe(
        "chat.stream_anonymous_reply",
        input=captured_input(content),
        metadata=metadata,
        tags=["chat", "anonymous"],
    ) as observation:
        async for event in stream_agent(anonymous_agent, deps, content, history_dicts):
            sse = format_sse_event(event)
            if sse:
                yield sse

            if event["event"] == "result":
                final_output = event["data"]["output"]
                usage_info = event["data"]["usage"]
            elif event["event"] == "error":
                safe_update(
                    observation,
                    output={"error": event["data"]},
                    metadata={**metadata, "status": "error"},
                )
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
