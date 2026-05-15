import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_active_user
from app.database import get_db
from app.models.user import User
from app.models.user_game import UserGameStatus
from app.schemas.psn_import import PSNConfirmRequest, PSNConfirmResponse, PSNPreviewRequest, PSNPreviewResponse
from app.schemas.steam_import import SteamConfirmRequest, SteamConfirmResponse, SteamPreviewRequest, SteamPreviewResponse
from app.schemas.user_game import UserGameCreate, UserGameRead, UserGameUpdate
from app.schemas.xbox_import import XboxConfirmRequest, XboxConfirmResponse, XboxPreviewRequest, XboxPreviewResponse
from app.services import psn_import as psn_service
from app.services import steam_import as steam_service
from app.services import user_games as ug_service
from app.services import xbox_import as xbox_service

router = APIRouter(prefix="/users/me/games", tags=["user_games"])


@router.get("", response_model=list[UserGameRead])
async def list_library(
    status: UserGameStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    return await ug_service.list_library(db, current_user.id, status)


@router.post("", response_model=UserGameRead, status_code=status.HTTP_201_CREATED)
async def add_to_library(
    payload: UserGameCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        return await ug_service.add_to_library(db, current_user.id, payload)
    except ValueError as e:
        if str(e) == "game_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jeu introuvable")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Jeu déjà dans la bibliothèque")


@router.patch("/{ug_id}", response_model=UserGameRead)
async def update_entry(
    ug_id: uuid.UUID,
    payload: UserGameUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    entry = await ug_service.update_entry(db, current_user.id, ug_id, payload)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrée introuvable")
    return entry


@router.delete("/{ug_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_entry(
    ug_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    removed = await ug_service.remove_entry(db, current_user.id, ug_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrée introuvable")


@router.post("/steam/preview", response_model=SteamPreviewResponse)
async def steam_preview(
    payload: SteamPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        items = await steam_service.build_preview(db, current_user, payload.profile)
    except ValueError as e:
        code = str(e)
        if code == "steam_invalid_input":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=code)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=code)
    return SteamPreviewResponse(items=items)


@router.post("/steam/import", response_model=SteamConfirmResponse)
async def steam_import(
    payload: SteamConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    imported, skipped = await steam_service.confirm_import(db, current_user, payload.items)
    return SteamConfirmResponse(imported=imported, skipped=skipped)


@router.post("/psn/preview", response_model=PSNPreviewResponse)
async def psn_preview(
    payload: PSNPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        items = await psn_service.build_preview(db, current_user, payload.online_id)
    except ValueError as e:
        code = str(e)
        if code in ("psn_npsso_invalid", "psn_api_unavailable"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=code)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=code)
    return PSNPreviewResponse(items=items)


@router.post("/psn/import", response_model=PSNConfirmResponse)
async def psn_import(
    payload: PSNConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    imported, skipped = await psn_service.confirm_import(db, current_user, payload.items)
    return PSNConfirmResponse(imported=imported, skipped=skipped)


@router.post("/xbox/preview", response_model=XboxPreviewResponse)
async def xbox_preview(
    payload: XboxPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        items = await xbox_service.build_preview(db, current_user, payload.gamertag)
    except ValueError as e:
        code = str(e)
        if code == "xbox_invalid_gamertag":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=code)
        if code == "xbox_profile_private":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=code)
        if code == "xbox_quota_exceeded":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=code)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=code)
    return XboxPreviewResponse(items=items)


@router.post("/xbox/import", response_model=XboxConfirmResponse)
async def xbox_import(
    payload: XboxConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    imported, skipped = await xbox_service.confirm_import(db, current_user, payload.items)
    return XboxConfirmResponse(imported=imported, skipped=skipped)
