import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.game import GameListResponse, GameRead
from app.services import games as game_service

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=GameListResponse)
async def list_games(
    q: str | None = Query(default=None),
    genre_slug: str | None = Query(default=None),
    platform_slug: str | None = Query(default=None),
    mode_slug: str | None = Query(default=None),
    tag_slug: str | None = Query(default=None),
    min_rating: float | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(current_active_user),
):
    items, total = await game_service.list_games(
        db, q=q, genre_slug=genre_slug, platform_slug=platform_slug,
        mode_slug=mode_slug, tag_slug=tag_slug, min_rating=min_rating,
        page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{game_id}", response_model=GameRead)
async def get_game(
    game_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(current_active_user),
):
    game = await game_service.get_game(db, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeu introuvable")
    return game
