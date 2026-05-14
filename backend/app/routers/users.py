from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_active_user
from app.auth.users import get_user_manager, UserManager
from app.database import get_db
from app.models.user import User
from app.schemas.user import DeleteAccountRequest, UserPatchMe, UserProfile
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    user = await user_service.get_user_with_relations(db, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user


@router.patch("/me", response_model=UserProfile)
async def patch_me(
    payload: UserPatchMe,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    user_data = payload.model_dump(exclude={"favorite_genre_ids", "important_criterion_ids"}, exclude_unset=True)
    if user_data:
        await user_manager.update(payload.__class__(**user_data), current_user, safe=True)

    if payload.favorite_genre_ids is not None:
        await user_service.set_favorite_genres(db, current_user.id, payload.favorite_genre_ids)

    if payload.important_criterion_ids is not None:
        await user_service.set_important_criteria(db, current_user.id, payload.important_criterion_ids)

    await db.commit()

    user = await user_service.get_user_with_relations(db, current_user.id)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    payload: DeleteAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    verified, _ = user_manager.password_helper.verify_and_update(
        payload.password, current_user.hashed_password
    )
    if not verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mot de passe incorrect")
    await user_service.delete_user(db, current_user)
