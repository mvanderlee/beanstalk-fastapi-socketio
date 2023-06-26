import datetime as dt
from typing import Any, Optional, Self, Type

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.exceptions import NotFound
from app.core.security import verify_password
from app.db import ActiveRecord, Base


class Role(ActiveRecord):
    name: Mapped[str]

    users: Mapped['RolesUsers'] = relationship(back_populates="role")


class RolesUsers(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('role.id'), primary_key=True)

    user: Mapped['User'] = relationship(back_populates="roles", uselist=False)
    role: Mapped['Role'] = relationship(back_populates="users", uselist=False)


class User(ActiveRecord):
    email: Mapped[str] = mapped_column(index=True, unique=True)

    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=False)
    confirmed_at: Mapped[Optional[dt.datetime]]

    last_login_at: Mapped[Optional[dt.datetime]]
    last_login_ip: Mapped[Optional[str]]

    reset_code_hash: Mapped[Optional[str]]
    reset_code_expiration: Mapped[Optional[dt.datetime]]

    roles: Mapped[RolesUsers] = relationship(back_populates="user")

    @classmethod
    async def aio_get_by_email(
        cls: Type[Self],
        email: str,
        session: AsyncSession,
        raise_if_not_found: bool = False,
    ) -> Self:
        result = await session.execute(
            select(User)
            .filter(User.email == email)
        )
        # Since we prevent duplicates on the API level, we assume there will only ever by one.
        entity = result.scalar_one_or_none()

        if entity is None and raise_if_not_found:
            raise NotFound('{} with id {} not found'.format(cls.__name__, id))

        return entity


    def verify_reset_code(self, code: str) -> bool:
        return (
            self.reset_code_hash
            and self.reset_code_expiration
            and self.reset_code_expiration > dt.datetime.now()
            and verify_password(code, self.reset_code_hash)
        )
