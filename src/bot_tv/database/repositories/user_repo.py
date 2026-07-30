from __future__ import annotations

from bot_tv.database.repositories.base import BaseRepository
from bot_tv.database.repositories.user_crud import UserCrudMixin
from bot_tv.database.repositories.user_queries import UserQueriesMixin
from bot_tv.database.repositories.user_roles import UserRolesMixin


class UserRepository(UserCrudMixin, UserRolesMixin, UserQueriesMixin, BaseRepository):
    """Repositorio para operaciones sobre las tablas users y channel_users."""

    pass
