"""
proposals_service — owns le cycle de vie complet d'une Proposal.

Seam unique pour l'invariant ADR-0015 :
"Aucune mutation Library ne peut avoir lieu sans MessageProposal confirmée par le user."

Toute mutation Library issue de l'agent passe obligatoirement par ce module :
    draft_* (validation pre-persist)
        → persist_drafts (INSERT atomique, génère les ids)
            → confirm (execute via Draft.execute + flip state, atomique)
              ou cancel (flip state seul)
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models.conversation import Message
from app.models.game import Game
from app.models.message_proposal import MessageProposal, ProposalState
from app.models.user_game import UserGame
from app.schemas.proposals import (
    AddToLibraryDraft,
    ChangeStatusDraft,
    ProposalDraft,
    RemoveFromLibraryDraft,
    SetRatingDraft,
    parse_draft,
)


# ─── Exceptions métier ───────────────────────────────────────────────────────


class ProposalError(Exception):
    """Erreur métier proposals. Le router HTTP les traduit en 4xx."""


class ProposalNotFound(ProposalError):
    pass


class ProposalForbidden(ProposalError):
    pass


class ProposalAlreadyCancelled(ProposalError):
    pass


class ProposalExecutionFailed(ProposalError):
    """L'exécution de la mutation Library a échoué (jeu absent, etc.)."""


# ─── Draft builders ──────────────────────────────────────────────────────────
# Validation pre-persist. Appelés par les tools agent.


async def draft_add_to_library(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    game_id: uuid.UUID,
    status_value: str | None = None,
    rating: int | None = None,
    review: str | None = None,
) -> AddToLibraryDraft | dict[str, Any]:
    """Construit un Draft 'add_to_library' ou retourne un dict d'erreur pour le LLM."""
    from app.models.user_game import UserGameStatus

    game = await db.get(Game, game_id)
    if not game:
        return {"error": "game_not_found"}

    existing = await db.execute(
        select(UserGame).where(UserGame.user_id == user_id, UserGame.game_id == game_id)
    )
    ug = existing.scalar_one_or_none()
    if ug:
        return {
            "error": "already_in_library",
            "user_game_id": str(ug.id),
            "current_status": ug.status.value if ug.status else None,
            "current_rating": ug.user_rating,
        }

    parsed_status: UserGameStatus | None = None
    if status_value:
        try:
            parsed_status = UserGameStatus(status_value)
        except ValueError:
            parsed_status = None

    if rating is not None and not (1 <= rating <= 10):
        return {"error": "invalid_rating", "message": "La note doit être entre 1 et 10."}

    return AddToLibraryDraft(
        game_id=game_id,
        title=game.title,
        cover_url=game.cover_url,
        status=parsed_status,
        rating=rating,
        review=review,
    )


async def _resolve_user_game(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    user_game_id: uuid.UUID | None,
    game_id: uuid.UUID | None,
) -> UserGame | None:
    """Helper partagé : récupère un UserGame appartenant au user par id ou par game_id."""
    if user_game_id:
        result = await db.execute(
            select(UserGame)
            .options(selectinload(UserGame.game))
            .where(UserGame.id == user_game_id, UserGame.user_id == user_id)
        )
        return result.scalar_one_or_none()
    if game_id:
        result = await db.execute(
            select(UserGame)
            .options(selectinload(UserGame.game))
            .where(UserGame.game_id == game_id, UserGame.user_id == user_id)
        )
        return result.scalar_one_or_none()
    return None


async def draft_change_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    new_status_value: str,
    user_game_id: uuid.UUID | None = None,
    game_id: uuid.UUID | None = None,
) -> ChangeStatusDraft | dict[str, Any]:
    from app.models.user_game import UserGameStatus

    try:
        new_status = UserGameStatus(new_status_value)
    except ValueError:
        return {"error": "invalid_status", "valid_values": [s.value for s in UserGameStatus]}

    if not user_game_id and not game_id:
        return {"error": "must_provide_user_game_id_or_game_id"}

    ug = await _resolve_user_game(db, user_id, user_game_id=user_game_id, game_id=game_id)
    if not ug:
        return {"error": "not_in_library"}

    return ChangeStatusDraft(
        user_game_id=ug.id,
        game_id=ug.game_id,
        title=ug.game.title,
        cover_url=ug.game.cover_url,
        current_status=ug.status,
        new_status=new_status,
    )


async def draft_set_rating(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    user_game_id: uuid.UUID | None = None,
    game_id: uuid.UUID | None = None,
    rating: int | None = None,
    review: str | None = None,
) -> SetRatingDraft | dict[str, Any]:
    if rating is not None and not (1 <= rating <= 10):
        return {"error": "invalid_rating", "message": "La note doit être entre 1 et 10."}

    if not user_game_id and not game_id:
        return {"error": "must_provide_user_game_id_or_game_id"}

    ug = await _resolve_user_game(db, user_id, user_game_id=user_game_id, game_id=game_id)
    if not ug:
        return {"error": "not_in_library"}

    return SetRatingDraft(
        user_game_id=ug.id,
        game_id=ug.game_id,
        title=ug.game.title,
        cover_url=ug.game.cover_url,
        current_rating=ug.user_rating,
        current_review=ug.review,
        rating=rating,
        review=review,
    )


async def draft_remove_from_library(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    user_game_id: uuid.UUID | None = None,
    game_id: uuid.UUID | None = None,
) -> RemoveFromLibraryDraft | dict[str, Any]:
    if not user_game_id and not game_id:
        return {"error": "must_provide_user_game_id_or_game_id"}

    ug = await _resolve_user_game(db, user_id, user_game_id=user_game_id, game_id=game_id)
    if not ug:
        return {"error": "not_in_library"}

    return RemoveFromLibraryDraft(
        user_game_id=ug.id,
        game_id=ug.game_id,
        title=ug.game.title,
        cover_url=ug.game.cover_url,
        current_status=ug.status,
    )


# ─── Persistance ─────────────────────────────────────────────────────────────


async def persist_drafts(
    db: AsyncSession, message_id: uuid.UUID, drafts: Sequence[ProposalDraft]
) -> list[MessageProposal]:
    """
    Insère les drafts en MessageProposal rows. Atomique (commit unique).
    Les ids sont générés ici, pas par les tools agent.

    Lève en cas d'échec — pas de swallow silencieux comme l'ancien chat.py.
    """
    if not drafts:
        return []

    rows: list[MessageProposal] = []
    for draft in drafts:
        row = MessageProposal(
            message_id=message_id,
            action_type=draft.action_type,
            payload=draft.to_storage_payload(),
        )
        db.add(row)
        rows.append(row)

    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


# ─── Confirm / Cancel ────────────────────────────────────────────────────────


async def _load_owned(
    db: AsyncSession, proposal_id: uuid.UUID, user_id: uuid.UUID
) -> MessageProposal:
    result = await db.execute(
        select(MessageProposal)
        .options(selectinload(MessageProposal.message).selectinload(Message.conversation))
        .where(MessageProposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise ProposalNotFound()
    if proposal.message.conversation.user_id != user_id:
        raise ProposalForbidden()
    return proposal


async def confirm(
    db: AsyncSession, user_id: uuid.UUID, proposal_id: uuid.UUID
) -> MessageProposal:
    """
    Exécute la mutation Library et flip l'état à 'confirmed'. Atomique.

    Invariants :
    - confirmed depuis pending uniquement (cancelled lève ProposalAlreadyCancelled)
    - confirmed déjà confirmed : idempotent (retourne la row inchangée)
    - si Draft.execute lève, l'état reste 'pending' (rollback)
    """
    proposal = await _load_owned(db, proposal_id, user_id)

    if proposal.state == ProposalState.confirmed:
        return proposal
    if proposal.state == ProposalState.cancelled:
        raise ProposalAlreadyCancelled()

    draft = parse_draft(proposal.action_type, proposal.payload)
    try:
        mutation_result = await draft.execute(db, user_id)
    except ValueError as exc:
        await db.rollback()
        raise ProposalExecutionFailed(str(exc))

    if mutation_result:
        merged = dict(proposal.payload)
        merged.update(mutation_result)
        proposal.payload = merged
        flag_modified(proposal, "payload")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(MessageProposal)
        .where(
            MessageProposal.id == proposal_id,
            MessageProposal.state == ProposalState.pending,
        )
        .values(state=ProposalState.confirmed, state_changed_at=now)
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def cancel(
    db: AsyncSession, user_id: uuid.UUID, proposal_id: uuid.UUID
) -> MessageProposal:
    """Flip l'état à 'cancelled'. Idempotent."""
    proposal = await _load_owned(db, proposal_id, user_id)

    if proposal.state in (ProposalState.confirmed, ProposalState.cancelled):
        return proposal

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(MessageProposal)
        .where(
            MessageProposal.id == proposal_id,
            MessageProposal.state == ProposalState.pending,
        )
        .values(state=ProposalState.cancelled, state_changed_at=now)
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal
