import json
import logging
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.services.proposals as proposals_service
from app.ai.agent import AgentDeps, agent
from app.ai.citations import cited_games_sse_event
from app.ai.stream import format_sse_event, stream_agent
from app.config import settings
from app.models.conversation import Conversation, Message, MessageRole
from app.models.user import User
from app.observability import captured_input, observe, safe_update
from app.schemas.conversation import ChatIntent
from app.schemas.proposals import ProposalDraft, parse_draft_dict
from app.services.chat_intents import short_circuit_response
from app.services.conversations import append_message

logger = logging.getLogger(__name__)


async def stream_reply(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    user_content: str,
    intent: ChatIntent | None = None,
) -> AsyncIterator[str]:
    """
    Orchestre le flux SSE complet :
    1. Sauvegarde le message utilisateur
    2. Charge l'historique (N derniers messages)
    3. Streame la réponse de l'agent
    4. Sauvegarde le message assistant avec tokens_used
    Yield : lignes SSE formatées (data: ...\n\n)
    """
    await append_message(db, conversation.id, MessageRole.user, user_content)

    canned = await short_circuit_response(db, user.id, intent)
    if canned is not None:
        assistant_msg = await append_message(db, conversation.id, MessageRole.assistant, canned, tokens_used=0)
        if conversation.title is None:
            conversation.title = user_content[:60]
            await db.commit()
        yield f"event: token\ndata: {json.dumps({'text': canned})}\n\n"
        yield f"event: done\ndata: {json.dumps({'assistant_message_id': str(assistant_msg.id), 'tokens_used': 0})}\n\n"
        logger.info("chat.intent_short_circuit", extra={
            "intent": intent.value if intent is not None else "none", "reason": "empty_library",
            "user_id": str(user.id), "conversation_id": str(conversation.id),
        })
        return

    history_result = await db.execute(
        select(Message)
        .options(selectinload(Message.proposals))
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(settings.chat_history_window + 1)
    )
    all_msgs = list(reversed(history_result.scalars().all()))
    history = all_msgs[:-1]

    user_with_relations = await db.execute(
        select(User)
        .options(selectinload(User.favorite_genres), selectinload(User.important_criteria))
        .where(User.id == user.id)
    )
    user_loaded = user_with_relations.scalar_one()

    deps = AgentDeps(db=db, user=user_loaded)

    final_output = ""
    usage_info = None
    pending_drafts: list[ProposalDraft] = []

    metadata = {
        "conversation_id": str(conversation.id),
        "model": settings.litellm_model,
        "route": "auth",
    }

    with observe(
        "chat.stream_reply",
        input=captured_input(user_content),
        metadata=metadata,
        user_id=str(user.id),
        session_id=str(conversation.id),
        tags=["chat", "auth"],
    ) as observation:
        async for event in stream_agent(agent, deps, user_content, history):
            sse = format_sse_event(event)
            if sse:
                yield sse

            # Side-effects spécifiques à l'agent auth :
            if event["event"] == "draft":
                # Collecte silencieuse — l'event SSE 'proposal' (avec id DB) sera
                # émis en fin de stream après persist_drafts.
                try:
                    pending_drafts.append(parse_draft_dict(event["data"]))
                except Exception as exc:
                    logger.warning("chat.draft_parse_error", extra={"error": str(exc), "data": event["data"]})
            elif event["event"] == "result":
                final_output = event["data"]["output"]
                usage_info = event["data"]["usage"]
            elif event["event"] == "error":
                safe_update(
                    observation,
                    output={"error": event["data"]},
                    metadata={**metadata, "status": "error"},
                )
                return

        if final_output:
            tokens = usage_info.get("total_tokens") if usage_info else None
            cache_read = usage_info.get("cache_read_tokens", 0) if usage_info else 0
            cache_write = usage_info.get("cache_write_tokens", 0) if usage_info else 0
            input_tokens = usage_info.get("input_tokens", 0) if usage_info else 0

            total_input = input_tokens + cache_read + cache_write
            hit_rate = cache_read / total_input if total_input > 0 else 0.0
            completion_metadata = {
                **metadata,
                "input_tokens": input_tokens,
                "cache_read_tokens": cache_read,
                "cache_write_tokens": cache_write,
                "total_tokens": tokens,
                "cache_hit_rate": round(hit_rate, 3),
                "status": "success",
            }
            logger.info("chat.completion", extra=completion_metadata)
            safe_update(
                observation,
                output=captured_input(final_output),
                metadata=completion_metadata,
            )

            cited_sse, cited_dicts = await cited_games_sse_event(db, final_output)
            if cited_sse:
                yield cited_sse

            assistant_msg = await append_message(
                db,
                conversation.id,
                MessageRole.assistant,
                final_output,
                tokens,
                cache_read_tokens=cache_read or None,
                cache_write_tokens=cache_write or None,
                cited_games=cited_dicts,
            )

            # Trade-off UX assumé : on persiste + émet les events `proposal` ICI
                # (fin du stream) plutôt qu'inline au moment du tool call.
                # Conséquence : les cartes apparaissent ~après la dernière ligne
                # du message au lieu de pendant l'écriture.
                # Pourquoi ce choix : l'id naît au persist (élimine les orphan ids
                # côté frontend). Une émission inline nécessiterait de créer le
                # Message assistant en début de stream pour avoir un message_id
                # disponible — refacto plus profond, à faire séparément si l'UX
                # le justifie (cf. TODO.md "Proposals inline pendant le stream").
            if pending_drafts:
                persisted = await proposals_service.persist_drafts(
                    db, assistant_msg.id, pending_drafts
                )
                for row in persisted:
                    proposal_event = {
                        "proposal_id": str(row.id),
                        "action_type": row.action_type.value,
                        **row.payload,
                    }
                    yield f"event: proposal\ndata: {json.dumps(proposal_event)}\n\n"

            if conversation.title is None:
                snippet = user_content.strip().splitlines()[0][:60]
                conversation.title = snippet if len(user_content.strip()) <= 60 else snippet + "…"
                await db.commit()
            yield f"event: done\ndata: {json.dumps({'assistant_message_id': str(assistant_msg.id), 'tokens_used': tokens})}\n\n"
