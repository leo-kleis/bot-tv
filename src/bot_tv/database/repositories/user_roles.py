from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class UserRolesMixin(BaseRepository):
    """Gestión de roles y relaciones de usuario por canal."""

    async def preload_cache(self, cache: UserMemoryCache) -> None:
        """Precarga todos los usuarios y sus roles desde PostgreSQL a la caché."""
        async with self._db.acquire() as conn:
            users_rows = await conn.fetch(
                "SELECT user_id, username, display_name, is_bot, nickname, "
                "profile_image_url FROM users"
            )
            roles_rows = await conn.fetch(
                "SELECT channel_id, user_id, followed_at, unfollowed_at, "
                "is_moderator, is_vip, is_subscriber, sub_tier FROM channel_users"
            )
        cache.preload([dict(r) for r in users_rows], [dict(r) for r in roles_rows])

    async def get_user_roles(
        self, user_id: str, channel_id: str, cache: UserMemoryCache | None = None
    ) -> dict[str, Any] | None:
        """Devuelve los roles (moderador, VIP, suscriptor) del usuario para un canal."""
        if cache is not None:
            cached_roles = cache.get_user_roles(user_id, channel_id)
            if cached_roles is not None:
                return cached_roles
        async with self._db.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id = $1", user_id
            )
            if not exists:
                return None

            query = (
                "SELECT is_moderator, is_vip, is_subscriber, sub_tier "
                "FROM channel_users WHERE user_id = $1 AND channel_id = $2"
            )
            row: asyncpg.Record | None = await conn.fetchrow(
                query,
                user_id,
                channel_id,
            )

        if not row:
            return {
                "is_moderator": False,
                "is_vip": False,
                "is_subscriber": False,
                "sub_tier": None,
            }
        return {
            "is_moderator": bool(row["is_moderator"]),
            "is_vip": bool(row["is_vip"]),
            "is_subscriber": bool(row["is_subscriber"]),
            "sub_tier": row["sub_tier"],
        }

    async def get_user_detail_by_name(
        self, username: str, channel_id: str
    ) -> dict[str, Any] | None:
        """Obtiene información de roles y seguimiento de un usuario."""
        query = """
            SELECT u.username, u.display_name, u.nickname, u.is_bot,
                   COALESCE(cu.is_moderator, FALSE) as is_moderator,
                   COALESCE(cu.is_vip, FALSE) as is_vip,
                   COALESCE(cu.is_subscriber, FALSE) as is_subscriber,
                   cu.followed_at, cu.unfollowed_at
            FROM users u
            LEFT JOIN channel_users cu ON u.user_id = cu.user_id AND cu.channel_id = $1
            WHERE u.username ILIKE $2
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                query, channel_id, username
            )
        if not row:
            return None
        return dict(row)

    async def update_user_roles(
        self,
        user_id: str,
        channel_id: str,
        is_bot: bool,
        is_moderator: bool,
        is_vip: bool,
        is_subscriber: bool | None = None,
        sub_tier: str | None = None,
        gifter_id: str | None = None,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Actualiza los roles de un usuario en la base de datos
        a nivel global y de canal.
        """
        if cache is not None:
            cache.set_user_bot(user_id, is_bot)
            cache.update_roles(
                channel_id,
                user_id,
                is_moderator,
                is_vip,
                is_subscriber if is_subscriber is not None else False,
                sub_tier,
            )

        LOGGER.info(
            "DB UPDATE roles para user_id %s (mod=%s, vip=%s, sub=%s)",
            user_id,
            is_moderator,
            is_vip,
            is_subscriber,
        )
        async with self._db.acquire() as conn:
            # 1. Actualizar is_bot global en users
            await conn.execute(
                "UPDATE users SET is_bot = $1 WHERE user_id = $2", is_bot, user_id
            )

            # 2. Upsert de roles a nivel de canal en channel_users
            if is_subscriber is not None:
                query = """
                    INSERT INTO channel_users (
                        channel_id, user_id, is_moderator, is_vip,
                        is_subscriber, sub_tier, gifter_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (channel_id, user_id)
                    DO UPDATE SET is_moderator  = EXCLUDED.is_moderator,
                                  is_vip        = EXCLUDED.is_vip,
                                  is_subscriber = EXCLUDED.is_subscriber,
                                  sub_tier      = EXCLUDED.sub_tier,
                                  gifter_id     = EXCLUDED.gifter_id
                """
                await conn.execute(
                    query,
                    channel_id,
                    user_id,
                    is_moderator,
                    is_vip,
                    is_subscriber,
                    sub_tier,
                    gifter_id,
                )
            else:
                query = """
                    INSERT INTO channel_users (
                        channel_id, user_id, is_moderator, is_vip
                    )
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (channel_id, user_id)
                    DO UPDATE SET is_moderator = EXCLUDED.is_moderator,
                                  is_vip       = EXCLUDED.is_vip
                """
                await conn.execute(query, channel_id, user_id, is_moderator, is_vip)
