import uuid
from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    def __init__(self, user_db: SQLAlchemyUserDatabase[User, uuid.UUID]) -> None:  # type: ignore[override]
        super().__init__(user_db)
        self._session: AsyncSession = user_db.session

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> Optional[User]:
        identifier = credentials.username
        result = await self._session.execute(
            select(User).where(
                or_(User.email == identifier, User.username == identifier)
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            self.password_helper.hash(credentials.password)
            return None
        verified, updated_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        if updated_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_hash})
        return user


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
