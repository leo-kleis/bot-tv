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
    ) -> bool:
        """Actualiza los roles de un usuario en la base de datos
        a level global y de canal solo si han cambiado. Retorna True si hubo cambios.
        """
        current_is_bot: bool | None = None
        current_mod: bool | None = None
        current_vip: bool | None = None
        current_sub: bool | None = None
        current_sub_tier: str | None = None
        current_gifter_id: str | None = None

        if cache is not None:
            user_data = cache.get_user(user_id)
            if user_data is not None:
                current_is_bot = bool(user_data.get("is_bot", False))
            roles_data = cache.get_user_roles(user_id, channel_id)
            if roles_data is not None:
                current_mod = bool(roles_data.get("is_moderator", False))
                current_vip = bool(roles_data.get("is_vip", False))
                current_sub = bool(roles_data.get("is_subscriber", False))
                current_sub_tier = roles_data.get("sub_tier")
                current_gifter_id = roles_data.get("gifter_id")

        if current_is_bot is None or current_mod is None:
            async with self._db.acquire() as conn:
                if current_is_bot is None:
                    user_row = await conn.fetchrow(
                        "SELECT is_bot FROM users WHERE user_id = $1", user_id
                    )
                    current_is_bot = bool(user_row["is_bot"]) if user_row else False
                if current_mod is None:
                    ch_row = await conn.fetchrow(
                        "SELECT is_moderator, is_vip, is_subscriber, "
                        "sub_tier, gifter_id "
                        "FROM channel_users WHERE channel_id = $1 AND user_id = $2",
                        channel_id,
                        user_id,
                    )
                    if ch_row:
                        current_mod = bool(ch_row["is_moderator"])
                        current_vip = bool(ch_row["is_vip"])
                        current_sub = bool(ch_row["is_subscriber"])
                        current_sub_tier = ch_row["sub_tier"]
                        current_gifter_id = ch_row["gifter_id"]
                    else:
                        current_mod = False
                        current_vip = False
                        current_sub = False
                        current_sub_tier = None
                        current_gifter_id = None

        bot_changed = current_is_bot != is_bot
        if is_subscriber is not None:
            roles_changed = (
                current_mod != is_moderator
                or current_vip != is_vip
                or current_sub != is_subscriber
                or current_sub_tier != sub_tier
                or current_gifter_id != gifter_id
            )
        else:
            roles_changed = current_mod != is_moderator or current_vip != is_vip

        if not bot_changed and not roles_changed:
            return False

        if cache is not None:
            cache.set_user_bot(user_id, is_bot)
            cache.update_roles(
                channel_id,
                user_id,
                is_moderator,
                is_vip,
                is_subscriber if is_subscriber is not None else (current_sub or False),
                sub_tier if is_subscriber is not None else current_sub_tier,
                gifter_id if is_subscriber is not None else current_gifter_id,
            )

        LOGGER.info(
            "DB UPDATE roles para user_id %s (mod=%s, vip=%s, sub=%s)",
            user_id,
            is_moderator,
            is_vip,
            is_subscriber,
        )
        async with self._db.acquire() as conn:
            # 1. Actualizar is_bot global en users solo si ha cambiado
            if bot_changed:
                await conn.execute(
                    "UPDATE users SET is_bot = $1 WHERE user_id = $2", is_bot, user_id
                )

            # 2. Upsert de roles a nivel de canal en channel_users solo si han cambiado
            if roles_changed:
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
        return True
