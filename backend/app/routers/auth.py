from fastapi import APIRouter

from app.auth.deps import fastapi_users, auth_backend
from app.schemas.user import UserCreate, UserRead

router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
)
