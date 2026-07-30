"""User repository."""
from __future__ import annotations

import uuid
from datetime import UTC

from sqlalchemy import select

from ..db.models import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            User.tenant_id == self.tenant_id, User.email == email.lower()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def create(
        self,
        email: str,
        password_hash: str,
        roles: list[str],
        display_name: str = "",
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
            roles=roles,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_login(self, user: User) -> None:
        from datetime import datetime

        user.last_login_at = datetime.now(UTC)
        await self.session.flush()
