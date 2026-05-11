import json
import logging
import uuid
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.ai.agent import AgentDeps
from app.ai.stream import stream_agent
from app.models.conversation import Conversation, Message, MessageRole
from app.models.message_proposal import MessageProposal, ProposalActionType, ProposalState
from app.models.user import User
from app.config import settings
from app.observability import captured_input, observe, safe_update
from app.services.conversations import append_message


async def stream_reply(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    user_content: str,
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
    pending_proposals: list[dict] = []

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
        async for event in stream_agent(deps, user_content, history):
            if event["event"] == "token":
                yield f"event: token\ndata: {json.dumps({'text': event['data']})}\n\n"
            elif event["event"] == "tool":
                yield f"event: tool\ndata: {json.dumps({'name': event['data']})}\n\n"
            elif event["event"] == "tool_call":
                yield f"event: tool_call\ndata: {json.dumps(event['data'])}\n\n"
            elif event["event"] == "tool_result":
                yield f"event: tool_result\ndata: {json.dumps(event['data'])}\n\n"
            elif event["event"] == "proposal":
                pending_proposals.append(event["data"])
                yield f"event: proposal\ndata: {json.dumps(event['data'])}\n\n"
            elif event["event"] == "result":
                final_output = event["data"]["output"]
                usage_info = event["data"]["usage"]
            elif event["event"] == "error":
                safe_update(
                    observation,
                    output={"error": event["data"]},
                    metadata={**metadata, "status": "error"},
                )
                yield f"event: error\ndata: {json.dumps({'message': event['data']})}\n\n"
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

            assistant_msg = await append_message(
                db,
                conversation.id,
                MessageRole.assistant,
                final_output,
                tokens,
                cache_read_tokens=cache_read or None,
                cache_write_tokens=cache_write or None,
            )

            for proposal_data in pending_proposals:
                try:
                    action_type = ProposalActionType(proposal_data["action_type"])
                    payload = {k: v for k, v in proposal_data.items() if k not in ("proposal_id", "action_type")}
                    db.add(MessageProposal(
                        id=uuid.UUID(proposal_data["proposal_id"]),
                        message_id=assistant_msg.id,
                        action_type=action_type,
                        payload=payload,
                    ))
                except Exception as exc:
                    logger.warning("chat.proposal_persist_error", extra={"error": str(exc)})
            if pending_proposals:
                await db.commit()

            if conversation.title is None:
                snippet = user_content.strip().splitlines()[0][:60]
                conversation.title = snippet if len(user_content.strip()) <= 60 else snippet + "…"
                await db.commit()
            yield f"event: done\ndata: {json.dumps({'assistant_message_id': str(assistant_msg.id), 'tokens_used': tokens})}\n\n"
