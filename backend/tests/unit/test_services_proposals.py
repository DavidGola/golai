"""
Tests d'invariants du seam proposals_service.

L'invariant central (ADR-0015) :
"Aucune mutation Library ne se produit sans MessageProposal confirmée."

Concrètement testé via :
- confirm depuis pending → mutation exécutée + state flippé
- confirm sur cancelled → ProposalAlreadyCancelled, aucune mutation
- échec d'execute → state reste pending, pas de mutation partielle
- persist_drafts ne swallow plus les erreurs (régression de l'ancien chat.py)
- ids générés au persist, pas par le caller
"""

import uuid

import pytest

from app.models.conversation import Message, MessageRole
from app.models.message_proposal import ProposalActionType, ProposalState
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.proposals import (
    AddToLibraryDraft,
    ChangeStatusDraft,
    RemoveFromLibraryDraft,
    SetRatingDraft,
)
import app.services.proposals as proposals_service
import app.services.user_games as ug_service
from app.schemas.user_game import UserGameCreate


# ─── Fixtures locales ────────────────────────────────────────────────────────


@pytest.fixture
async def assistant_message(db_session, conversation_a):
    msg = Message(
        conversation_id=conversation_a.id,
        role=MessageRole.assistant,
        content="...",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    return msg


@pytest.fixture
async def library_entry(db_session, user_a, seeded_game):
    return await ug_service.add_to_library(
        db_session,
        user_a.id,
        UserGameCreate(game_id=seeded_game.id, status=UserGameStatus.todo),
    )


def _add_draft(game) -> AddToLibraryDraft:
    return AddToLibraryDraft(
        game_id=game.id,
        title=game.title,
        cover_url=None,
        status=UserGameStatus.todo,
    )


# ─── persist_drafts ──────────────────────────────────────────────────────────


async def test_persist_drafts_generates_ids_and_inserts_rows(
    db_session, assistant_message, seeded_game
):
    drafts = [_add_draft(seeded_game)]
    rows = await proposals_service.persist_drafts(db_session, assistant_message.id, drafts)

    assert len(rows) == 1
    row = rows[0]
    assert row.id is not None  # ← id généré par le service, pas par le caller
    assert row.action_type == ProposalActionType.add_to_library
    assert row.state == ProposalState.pending
    assert row.payload["game_id"] == str(seeded_game.id)


async def test_persist_drafts_empty_list_is_noop(db_session, assistant_message):
    rows = await proposals_service.persist_drafts(db_session, assistant_message.id, [])
    assert rows == []


async def test_persist_drafts_raises_on_invalid_message_id(db_session, seeded_game):
    """Régression : l'ancien chat.py swallow les erreurs de persist. Le service doit raise."""
    drafts = [_add_draft(seeded_game)]
    with pytest.raises(Exception):
        await proposals_service.persist_drafts(db_session, uuid.uuid4(), drafts)


# ─── confirm : invariant pending → confirmed exécute la mutation ─────────────


async def test_confirm_pending_add_executes_mutation_and_flips_state(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )

    confirmed = await proposals_service.confirm(db_session, user_a.id, proposal.id)

    assert confirmed.state == ProposalState.confirmed
    assert confirmed.state_changed_at is not None
    # La mutation a été exécutée : un UserGame existe désormais
    from sqlalchemy import select
    found = (await db_session.execute(
        select(UserGame).where(UserGame.user_id == user_a.id, UserGame.game_id == seeded_game.id)
    )).scalar_one_or_none()
    assert found is not None
    # Le payload a été enrichi avec result_user_game_id
    assert confirmed.payload.get("result_user_game_id") == str(found.id)


# ─── confirm : idempotence et état terminal ──────────────────────────────────


async def test_confirm_already_confirmed_is_idempotent(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )
    await proposals_service.confirm(db_session, user_a.id, proposal.id)
    # second appel ne re-exécute rien et ne raise pas
    again = await proposals_service.confirm(db_session, user_a.id, proposal.id)
    assert again.state == ProposalState.confirmed


async def test_confirm_after_cancel_raises(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )
    await proposals_service.cancel(db_session, user_a.id, proposal.id)

    with pytest.raises(proposals_service.ProposalAlreadyCancelled):
        await proposals_service.confirm(db_session, user_a.id, proposal.id)


# ─── confirm : invariant central — échec d'execute = state reste pending ─────


async def test_confirm_failed_execute_does_not_flip_state(
    db_session, user_a, assistant_message
):
    """
    Invariant ADR-0015 : si la mutation Library échoue, la Proposal reste pending.
    Pas de moitié de transaction qui flippe le state sans mutation.
    """
    # Draft remove_from_library qui pointe vers un UserGame inexistant
    bad_draft = RemoveFromLibraryDraft(
        user_game_id=uuid.uuid4(),  # n'existe pas
        game_id=uuid.uuid4(),
        title="ghost",
    )
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [bad_draft]
    )

    with pytest.raises(proposals_service.ProposalExecutionFailed):
        await proposals_service.confirm(db_session, user_a.id, proposal.id)

    # Vérifie l'invariant : state inchangé
    await db_session.refresh(proposal)
    assert proposal.state == ProposalState.pending


# ─── Authorization ───────────────────────────────────────────────────────────


async def test_confirm_other_user_proposal_raises_forbidden(
    db_session, user_a, user_b, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )

    with pytest.raises(proposals_service.ProposalForbidden):
        await proposals_service.confirm(db_session, user_b.id, proposal.id)


async def test_confirm_unknown_proposal_raises_not_found(db_session, user_a):
    with pytest.raises(proposals_service.ProposalNotFound):
        await proposals_service.confirm(db_session, user_a.id, uuid.uuid4())


# ─── cancel : idempotence ────────────────────────────────────────────────────


async def test_cancel_pending_flips_state(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )
    cancelled = await proposals_service.cancel(db_session, user_a.id, proposal.id)
    assert cancelled.state == ProposalState.cancelled


async def test_cancel_already_cancelled_is_idempotent(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )
    await proposals_service.cancel(db_session, user_a.id, proposal.id)
    again = await proposals_service.cancel(db_session, user_a.id, proposal.id)
    assert again.state == ProposalState.cancelled


async def test_cancel_already_confirmed_is_noop(
    db_session, user_a, assistant_message, seeded_game
):
    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [_add_draft(seeded_game)]
    )
    await proposals_service.confirm(db_session, user_a.id, proposal.id)
    cancelled_attempt = await proposals_service.cancel(db_session, user_a.id, proposal.id)
    # cancel sur une row déjà confirmed ne change rien
    assert cancelled_attempt.state == ProposalState.confirmed


# ─── Draft builders : validation pre-persist ─────────────────────────────────


async def test_draft_add_rejects_game_already_in_library(
    db_session, user_a, library_entry, seeded_game
):
    """
    Un add_to_library pour un Game déjà en Library retourne un dict d'erreur,
    pas un Draft. C'est ce signal qui empêche la persistance d'une Proposal absurde.
    """
    result = await proposals_service.draft_add_to_library(
        db_session, user_a.id, game_id=seeded_game.id
    )
    assert isinstance(result, dict)
    assert result["error"] == "already_in_library"


async def test_draft_add_unknown_game_returns_error(db_session, user_a):
    result = await proposals_service.draft_add_to_library(
        db_session, user_a.id, game_id=uuid.uuid4()
    )
    assert isinstance(result, dict)
    assert result["error"] == "game_not_found"


async def test_draft_change_status_unknown_user_game_returns_error(db_session, user_a):
    result = await proposals_service.draft_change_status(
        db_session, user_a.id, new_status_value="completed", user_game_id=uuid.uuid4()
    )
    assert isinstance(result, dict)
    assert result["error"] == "not_in_library"


async def test_draft_change_status_invalid_status_returns_error(
    db_session, user_a, library_entry
):
    result = await proposals_service.draft_change_status(
        db_session, user_a.id, new_status_value="invalid", user_game_id=library_entry.id
    )
    assert isinstance(result, dict)
    assert result["error"] == "invalid_status"


async def test_draft_change_status_happy_path(db_session, user_a, library_entry):
    result = await proposals_service.draft_change_status(
        db_session,
        user_a.id,
        new_status_value="completed",
        user_game_id=library_entry.id,
    )
    assert isinstance(result, ChangeStatusDraft)
    assert result.new_status == UserGameStatus.completed
    assert result.user_game_id == library_entry.id


async def test_draft_set_rating_invalid_rating_returns_error(
    db_session, user_a, library_entry
):
    result = await proposals_service.draft_set_rating(
        db_session, user_a.id, user_game_id=library_entry.id, rating=42
    )
    assert isinstance(result, dict)
    assert result["error"] == "invalid_rating"


async def test_draft_set_rating_happy_path(db_session, user_a, library_entry):
    result = await proposals_service.draft_set_rating(
        db_session,
        user_a.id,
        user_game_id=library_entry.id,
        rating=8,
        review="cool",
    )
    assert isinstance(result, SetRatingDraft)
    assert result.rating == 8


# ─── Cycle complet : draft → persist → confirm met à jour la Library ─────────


async def test_full_cycle_change_status_mutates_library(
    db_session, user_a, library_entry, assistant_message
):
    """End-to-end : Draft → persist → confirm → vérifie que UserGame.status a changé."""
    assert library_entry.status == UserGameStatus.todo

    draft = await proposals_service.draft_change_status(
        db_session,
        user_a.id,
        new_status_value="completed",
        user_game_id=library_entry.id,
    )
    assert isinstance(draft, ChangeStatusDraft)

    [proposal] = await proposals_service.persist_drafts(
        db_session, assistant_message.id, [draft]
    )
    await proposals_service.confirm(db_session, user_a.id, proposal.id)

    await db_session.refresh(library_entry)
    assert library_entry.status == UserGameStatus.completed
