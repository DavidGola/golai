import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.models.message_proposal import ProposalActionType, ProposalState
from app.models.user_game import UserGameStatus


# ============================================================
# Drafts — intents produits par les tools agent.
# Pas d'id, pas de state, pas persistés tels quels (la sérialisation JSONB
# passe par to_storage_payload pour rester compatible avec le contrat existant
# côté frontend : champs `current` et `target` nichés).
# Chaque Draft porte sa propre logique d'exécution (.execute) — pas de dispatch
# par enum.
# ============================================================


class _DraftBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddToLibraryDraft(_DraftBase):
    action_type: Literal[ProposalActionType.add_to_library] = ProposalActionType.add_to_library
    game_id: uuid.UUID
    title: str
    cover_url: str | None = None
    status: UserGameStatus | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "game_id": str(self.game_id),
            "title": self.title,
            "cover_url": self.cover_url,
            "status": self.status.value if self.status else None,
            "rating": self.rating,
            "review": self.review,
            "current": None,
            "target": {
                "status": self.status.value if self.status else None,
                "rating": self.rating,
                "review": self.review,
            },
        }

    async def execute(self, db, user_id: uuid.UUID) -> dict[str, Any]:
        from app.schemas.user_game import UserGameCreate
        from app.services import user_games as ug_service

        new_ug = await ug_service.add_to_library(
            db,
            user_id,
            UserGameCreate(
                game_id=self.game_id,
                status=self.status,
                user_rating=self.rating,
                review=self.review,
            ),
        )
        return {"result_user_game_id": str(new_ug.id)}


class ChangeStatusDraft(_DraftBase):
    action_type: Literal[ProposalActionType.change_status] = ProposalActionType.change_status
    user_game_id: uuid.UUID
    game_id: uuid.UUID
    title: str
    cover_url: str | None = None
    current_status: UserGameStatus | None = None
    new_status: UserGameStatus

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "user_game_id": str(self.user_game_id),
            "game_id": str(self.game_id),
            "title": self.title,
            "cover_url": self.cover_url,
            "new_status": self.new_status.value,
            "current": {"status": self.current_status.value if self.current_status else None},
            "target": {"status": self.new_status.value},
        }

    async def execute(self, db, user_id: uuid.UUID) -> dict[str, Any]:
        from app.schemas.user_game import UserGameUpdate
        from app.services import user_games as ug_service

        result = await ug_service.update_entry(
            db, user_id, self.user_game_id, UserGameUpdate(status=self.new_status)
        )
        if not result:
            raise ValueError("user_game_not_found")
        return {}


class SetRatingDraft(_DraftBase):
    action_type: Literal[ProposalActionType.set_rating] = ProposalActionType.set_rating
    user_game_id: uuid.UUID
    game_id: uuid.UUID
    title: str
    cover_url: str | None = None
    current_rating: int | None = None
    current_review: str | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "user_game_id": str(self.user_game_id),
            "game_id": str(self.game_id),
            "title": self.title,
            "cover_url": self.cover_url,
            "rating": self.rating,
            "review": self.review,
            "current": {"rating": self.current_rating, "review": self.current_review},
            "target": {"rating": self.rating, "review": self.review},
        }

    async def execute(self, db, user_id: uuid.UUID) -> dict[str, Any]:
        from app.schemas.user_game import UserGameUpdate
        from app.services import user_games as ug_service

        result = await ug_service.update_entry(
            db,
            user_id,
            self.user_game_id,
            UserGameUpdate(user_rating=self.rating, review=self.review),
        )
        if not result:
            raise ValueError("user_game_not_found")
        return {}


class RemoveFromLibraryDraft(_DraftBase):
    action_type: Literal[ProposalActionType.remove_from_library] = ProposalActionType.remove_from_library
    user_game_id: uuid.UUID
    game_id: uuid.UUID
    title: str
    cover_url: str | None = None
    current_status: UserGameStatus | None = None

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "user_game_id": str(self.user_game_id),
            "game_id": str(self.game_id),
            "title": self.title,
            "cover_url": self.cover_url,
            "current": {"status": self.current_status.value if self.current_status else None},
            "target": None,
        }

    async def execute(self, db, user_id: uuid.UUID) -> dict[str, Any]:
        from app.services import user_games as ug_service

        removed = await ug_service.remove_entry(db, user_id, self.user_game_id)
        if not removed:
            raise ValueError("user_game_not_found")
        return {}


ProposalDraft = Annotated[
    Union[
        AddToLibraryDraft,
        ChangeStatusDraft,
        SetRatingDraft,
        RemoveFromLibraryDraft,
    ],
    Field(discriminator="action_type"),
]

_draft_adapter: TypeAdapter[
    AddToLibraryDraft | ChangeStatusDraft | SetRatingDraft | RemoveFromLibraryDraft
] = TypeAdapter(ProposalDraft)


# ─── Parseurs : storage JSONB ↔ Draft typé ───────────────────────────────────


def _storage_to_draft_dict(action_type: ProposalActionType, payload: dict[str, Any]) -> dict[str, Any]:
    """Convertit le payload JSONB (legacy shape avec current/target) vers les
    champs flat attendus par le Draft Pydantic."""
    base: dict[str, Any] = {
        "action_type": action_type,
        "title": payload.get("title", ""),
        "cover_url": payload.get("cover_url"),
        "game_id": payload.get("game_id"),
    }

    if action_type == ProposalActionType.add_to_library:
        base.update({
            "status": payload.get("status"),
            "rating": payload.get("rating"),
            "review": payload.get("review"),
        })
        return base

    if action_type == ProposalActionType.change_status:
        current = payload.get("current") or {}
        target = payload.get("target") or {}
        base.update({
            "user_game_id": payload.get("user_game_id"),
            "current_status": current.get("status"),
            "new_status": payload.get("new_status") or target.get("status"),
        })
        return base

    if action_type == ProposalActionType.set_rating:
        current = payload.get("current") or {}
        base.update({
            "user_game_id": payload.get("user_game_id"),
            "current_rating": current.get("rating"),
            "current_review": current.get("review"),
            "rating": payload.get("rating"),
            "review": payload.get("review"),
        })
        return base

    if action_type == ProposalActionType.remove_from_library:
        current = payload.get("current") or {}
        base.update({
            "user_game_id": payload.get("user_game_id"),
            "current_status": current.get("status"),
        })
        return base

    raise ValueError(f"unknown action_type: {action_type}")


def parse_draft(action_type: ProposalActionType, payload: dict[str, Any]) -> (
    AddToLibraryDraft | ChangeStatusDraft | SetRatingDraft | RemoveFromLibraryDraft
):
    """Parse un payload JSONB (legacy shape) stocké en row MessageProposal vers
    le Draft typé correspondant."""
    draft_dict = _storage_to_draft_dict(action_type, payload)
    return _draft_adapter.validate_python(draft_dict)


def parse_draft_dict(data: dict[str, Any]) -> (
    AddToLibraryDraft | ChangeStatusDraft | SetRatingDraft | RemoveFromLibraryDraft
):
    """Parse un dict (qui contient déjà action_type au format flat) vers le Draft typé.
    Utilisé pour reconvertir un event SSE 'draft' (Draft.model_dump) en Pydantic typé."""
    return _draft_adapter.validate_python(data)


# ============================================================
# ProposalRead — vue HTTP existante. Conservée à l'identique pour ne pas casser
# le contrat REST côté frontend.
# ============================================================


class ProposalRead(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    action_type: ProposalActionType
    payload: dict[str, Any]
    state: ProposalState
    state_changed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
