from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import BaseRepository, to_iso_str

if TYPE_CHECKING:
    import asyncpg

    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class UserRolesMixin(BaseRepository):
    """Gestión de roles y relaciones de usuario por canal."""

    async def preload_cache(self, cache: UserMemoryCache) -> None:
        """Precarga todos los usuarios y sus roles desde PostgreSQL a la caché."""

        async def _fetch_all(
            conn: asyncpg.Connection,
        ) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
            users_rows = await conn.fetch(
                "SELECT user_id, username, display_name, is_bot, nickname, "
                "profile_image_url FROM users"
            )
            roles_rows = await conn.fetch(
                "SELECT channel_id, user_id, followed_at, unfollowed_at, "
                "is_moderator, is_vip, is_subscriber, sub_tier, gifter_id "
                "FROM channel_users"
            )
            return users_rows, roles_rows

        users_rows, roles_rows = await self._with_retry(
            _fetch_all, context_label="preload_cache"
        )
        cache.preload(users_rows, roles_rows)

    async def get_user_roles(
        self, user_id: str, channel_id: str, cache: UserMemoryCache | None = None
    ) -> dict[str, Any] | None:
        """Devuelve los roles (moderador, VIP, suscriptor) del usuario para un canal."""
        if cache is not None and cache.has_users:
            cached_roles = cache.get_user_roles(user_id, channel_id)
            if cached_roles is not None:
                return cached_roles
        query = (
            "SELECT u.user_id, cu.is_moderator, cu.is_vip, "
            "cu.is_subscriber, cu.sub_tier "
            "FROM users u "
            "LEFT JOIN channel_users cu "
            "ON u.user_id = cu.user_id AND cu.channel_id = $2 "
            "WHERE u.user_id = $1"
        )
        row = await self._fetchrow(
            query, user_id, channel_id, context_label="get_user_roles"
        )

        if not row:
            return None
        return {
            "is_moderator": bool(row["is_moderator"]),
            "is_vip": bool(row["is_vip"]),
            "is_subscriber": bool(row["is_subscriber"]),
            "sub_tier": row["sub_tier"],
        }

    async def get_user_detail_by_name(
        self,
        username: str,
        channel_id: str,
        cache: UserMemoryCache | None = None,
    ) -> dict[str, Any] | None:
        """Obtiene información de roles y seguimiento de un usuario."""
        if cache is not None and cache.has_users:
            cached_detail = cache.get_user_detail_by_name(username, channel_id)
            if cached_detail is not None:
                return cached_detail

        query = """
            SELECT u.user_id, u.username, u.display_name, u.nickname, u.is_bot,
                   COALESCE(cu.is_moderator, FALSE) as is_moderator,
                   COALESCE(cu.is_vip, FALSE) as is_vip,
                   COALESCE(cu.is_subscriber, FALSE) as is_subscriber,
                   cu.sub_tier, cu.followed_at, cu.unfollowed_at
            FROM users u
            LEFT JOIN channel_users cu ON u.user_id = cu.user_id AND cu.channel_id = $1
            WHERE LOWER(u.username) = LOWER($2)
        """
        row = await self._fetchrow(
            query, channel_id, username, context_label="get_user_detail_by_name"
        )
        if not row:
            return None
        result = dict(row)
        result["followed_at"] = to_iso_str(result.get("followed_at"))
        result["unfollowed_at"] = to_iso_str(result.get("unfollowed_at"))
        return result

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

        if cache is not None and cache.has_users:
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

            async def _fetch_missing_state(
                conn: asyncpg.Connection,
            ) -> tuple[bool, bool, bool, bool, str | None, str | None]:
                bot_flag = current_is_bot
                if bot_flag is None:
                    user_row = await conn.fetchrow(
                        "SELECT is_bot FROM users WHERE user_id = $1", user_id
                    )
                    bot_flag = bool(user_row["is_bot"]) if user_row else False

                mod_flag = current_mod
                vip_flag = current_vip if current_vip is not None else False
                sub_flag = current_sub if current_sub is not None else False
                tier_val = current_sub_tier
                gifter_val = current_gifter_id

                if mod_flag is None:
                    ch_row = await conn.fetchrow(
                        "SELECT is_moderator, is_vip, is_subscriber, "
                        "sub_tier, gifter_id "
                        "FROM channel_users WHERE channel_id = $1 AND user_id = $2",
                        channel_id,
                        user_id,
                    )
                    if ch_row:
                        mod_flag = bool(ch_row["is_moderator"])
                        vip_flag = bool(ch_row["is_vip"])
                        sub_flag = bool(ch_row["is_subscriber"])
                        tier_val = ch_row["sub_tier"]
                        gifter_val = ch_row["gifter_id"]
                    else:
                        mod_flag = False
                        vip_flag = False
                        sub_flag = False
                        tier_val = None
                        gifter_val = None

                return bot_flag, mod_flag, vip_flag, sub_flag, tier_val, gifter_val

            (
                current_is_bot,
                current_mod,
                current_vip,
                current_sub,
                current_sub_tier,
                current_gifter_id,
            ) = await self._with_retry(
                _fetch_missing_state, context_label="update_user_roles.fetch"
            )

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

        LOGGER.info(
            "DB UPDATE roles para user_id %s (mod=%s, vip=%s, sub=%s)",
            user_id,
            is_moderator,
            is_vip,
            is_subscriber,
        )

        async def _apply_role_updates(conn: asyncpg.Connection) -> None:
            if bot_changed:
                await conn.execute(
                    "UPDATE users SET is_bot = $1 WHERE user_id = $2", is_bot, user_id
                )

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

        await self._with_transaction(
            _apply_role_updates, context_label="update_user_roles"
        )

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

        return True
