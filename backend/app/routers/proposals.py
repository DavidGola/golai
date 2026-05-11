import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.auth.deps import current_active_user
from app.database import get_db
from app.models.conversation import Message
from app.models.message_proposal import MessageProposal, ProposalActionType, ProposalState
from app.models.user import User
from app.models.user_game import UserGameStatus
from app.schemas.proposals import ProposalRead
from app.schemas.user_game import UserGameCreate, UserGameUpdate
from app.services import user_games as ug_service

router = APIRouter(prefix="/proposals", tags=["proposals"])


async def _get_owned_proposal(
    db: AsyncSession, proposal_id: uuid.UUID, user_id: uuid.UUID
) -> MessageProposal:
    result = await db.execute(
        select(MessageProposal)
        .options(
            selectinload(MessageProposal.message).selectinload(Message.conversation)
        )
        .where(MessageProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposition introuvable")
    if proposal.message.conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    return proposal


async def _execute_mutation(
    db: AsyncSession, proposal: MessageProposal, user_id: uuid.UUID
) -> dict | None:
    payload = proposal.payload
    action = proposal.action_type

    if action == ProposalActionType.add_to_library:
        game_id = uuid.UUID(payload["game_id"])
        raw_status = payload.get("status")
        s = UserGameStatus(raw_status) if raw_status else None
        new_ug = await ug_service.add_to_library(
            db,
            user_id,
            UserGameCreate(
                game_id=game_id,
                status=s,
                user_rating=payload.get("rating"),
                review=payload.get("review"),
            ),
        )
        return {"result_user_game_id": str(new_ug.id)}

    elif action == ProposalActionType.change_status:
        ug_id = uuid.UUID(payload["user_game_id"])
        new_status = UserGameStatus(payload["new_status"])
        result = await ug_service.update_entry(db, user_id, ug_id, UserGameUpdate(status=new_status))
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeu introuvable dans la bibliothèque")

    elif action == ProposalActionType.set_rating:
        ug_id = uuid.UUID(payload["user_game_id"])
        rating = payload.get("rating")
        review = payload.get("review")
        result = await ug_service.update_entry(
            db, user_id, ug_id, UserGameUpdate(user_rating=rating, review=review)
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeu introuvable dans la bibliothèque")

    elif action == ProposalActionType.remove_from_library:
        ug_id = uuid.UUID(payload["user_game_id"])
        removed = await ug_service.remove_entry(db, user_id, ug_id)
        if not removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeu introuvable dans la bibliothèque")

    return None


@router.post("/{proposal_id}/confirm", response_model=ProposalRead)
async def confirm_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    proposal = await _get_owned_proposal(db, proposal_id, current_user.id)

    if proposal.state == ProposalState.confirmed:
        return proposal
    if proposal.state == ProposalState.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette proposition a déjà été annulée",
        )

    try:
        mutation_result = await _execute_mutation(db, proposal, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if mutation_result:
        merged = dict(proposal.payload)
        merged.update(mutation_result)
        proposal.payload = merged
        flag_modified(proposal, "payload")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(MessageProposal)
        .where(MessageProposal.id == proposal_id, MessageProposal.state == ProposalState.pending)
        .values(state=ProposalState.confirmed, state_changed_at=now)
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal


@router.post("/{proposal_id}/cancel", response_model=ProposalRead)
async def cancel_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    proposal = await _get_owned_proposal(db, proposal_id, current_user.id)

    if proposal.state in (ProposalState.confirmed, ProposalState.cancelled):
        return proposal

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(MessageProposal)
        .where(MessageProposal.id == proposal_id, MessageProposal.state == ProposalState.pending)
        .values(state=ProposalState.cancelled, state_changed_at=now)
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal
