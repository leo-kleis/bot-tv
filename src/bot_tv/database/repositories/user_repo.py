from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla users."""

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

    async def upsert_user(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Inserta o actualiza un usuario (sin tocar el nickname si ya existe)."""
        if cache is not None:
            if not cache.needs_user_update(user_id, username, display_name):
                return
            cache.update_user(user_id, username, display_name)

        LOGGER.info(
            "DB UPDATE/INSERT usuario en PostgreSQL: %s (ID: %s)", username, user_id
        )
        query = """
            INSERT INTO users (user_id, username, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET username      = EXCLUDED.username,
                          display_name  = EXCLUDED.display_name
        """
        async with self._db.acquire() as conn:
            await conn.execute(
                query,
                user_id,
                username,
                display_name,
            )

    async def get_user_nickname(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve el nickname del usuario, o None si no tiene."""
        if cache is not None:
            return cache.get_user_nickname(user_id)
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT nickname FROM users WHERE user_id = $1", user_id
            )
        return row["nickname"] if row else None

    async def get_user_id_by_name(
        self, username: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve el user_id de un usuario a partir de su username."""
        if cache is not None:
            cached_id = cache.get_user_id_by_name(username)
            if cached_id is not None:
                return cached_id
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT user_id FROM users WHERE username ILIKE $1",
                username,
            )
        return row["user_id"] if row else None

    async def set_nickname(
        self, user_id: str, nickname: str | None, cache: UserMemoryCache | None = None
    ) -> None:
        """Establece o elimina el apodo personalizado de un usuario."""
        if cache is not None:
            cache.set_nickname(user_id, nickname)
        LOGGER.info("DB UPDATE apodo para user_id %s: %s", user_id, nickname)
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET nickname = $1 WHERE user_id = $2",
                nickname,
                user_id,
            )

    async def is_user_bot(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> bool:
        """Devuelve True si el usuario está marcado como bot en la DB."""
        if cache is not None:
            return cache.is_user_bot(user_id)
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT is_bot FROM users WHERE user_id = $1", user_id
            )
        return bool(row["is_bot"]) if row else False

    async def set_user_bot(
        self, user_id: str, is_bot: bool, cache: UserMemoryCache | None = None
    ) -> None:
        """Marca o desmarca un usuario como bot."""
        if cache is not None:
            cache.set_user_bot(user_id, is_bot)
        LOGGER.info("DB UPDATE bot status para user_id %s: %s", user_id, is_bot)
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_bot = $1 WHERE user_id = $2",
                is_bot,
                user_id,
            )

    async def get_users_info(
        self, user_ids: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Devuelve info de visualización para los IDs de usuario dados."""
        if not user_ids:
            return {}
        query = (
            "SELECT user_id, display_name, nickname FROM users WHERE user_id = ANY($1)"
        )
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, user_ids)
        return {
            row["user_id"]: {
                "display_name": row["display_name"],
                "nickname": row["nickname"],
            }
            for row in rows
        }

    async def get_unfollowers_data(
        self, channel_id: str, user_ids: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Devuelve info completa para usuarios que dejaron de seguir."""
        if not user_ids:
            return {}
        query = (
            "SELECT u.user_id, u.display_name, u.nickname, cu.followed_at"
            " FROM users u JOIN channel_users cu ON u.user_id = cu.user_id"
            " WHERE cu.channel_id = $1 AND cu.user_id = ANY($2)"
        )
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, user_ids)
        return {
            row["user_id"]: {
                "display_name": row["display_name"],
                "nickname": row["nickname"],
                "followed_at": row["followed_at"],
            }
            for row in rows
        }

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

    async def list_users_with_filters(
        self,
        channel_id: str,
        broadcaster_id: str | None = None,
        role: str | None = None,
        has_nickname: bool | None = None,
        username_search: str | None = None,
        followed_after: str | None = None,
        followed_before: str | None = None,
        unfollowed_after: str | None = None,
        unfollowed_before: str | None = None,
        is_follower: str | None = None,
        sort_by: str = "username",
        sort_order: str = "asc",
        limit: int = 20,
        offset: int = 0,
        cache: UserMemoryCache | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Devuelve usuarios registrados filtrados y el total coincidente."""
        if cache is not None:
            users, total = cache.list_users_with_filters(
                channel_id=channel_id,
                broadcaster_id=broadcaster_id,
                role=role,
                username_search=username_search,
                followed_after=followed_after,
                followed_before=followed_before,
                unfollowed_after=unfollowed_after,
                unfollowed_before=unfollowed_before,
                is_follower=is_follower,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset,
            )
            # El caché no tiene acceso a chat_history; se obtienen los conteos
            # con un único query batch sobre los user_ids de la página actual.
            if users:
                user_ids = [u["user_id"] for u in users if u.get("user_id")]
                counts = await self._fetch_message_counts_batch(channel_id, user_ids)
                for u in users:
                    u["message_count"] = counts.get(u.get("user_id", ""), 0)
            return users, total

        limit = max(1, limit)
        offset = max(0, offset)
        where_clauses: list[str] = []
        params: list[Any] = [channel_id]

        def _p() -> str:
            """Retorna el próximo placeholder numerado."""
            return f"${len(params) + 1}"

        if role:
            role_clean = role.lower()
            if role_clean in ("bot", "bots"):
                where_clauses.append("u.is_bot = TRUE")
            elif role_clean in ("moderator", "moderador", "mods", "mod"):
                where_clauses.append("cu.is_moderator = TRUE")
            elif role_clean in ("vip", "vips"):
                where_clauses.append("cu.is_vip = TRUE")
            elif role_clean in (
                "subscriber",
                "suscriptor",
                "subscribers",
                "sub",
                "subs",
            ):
                where_clauses.append("cu.is_subscriber = TRUE")

        if has_nickname is not None:
            if has_nickname:
                where_clauses.append("u.nickname IS NOT NULL AND u.nickname != ''")
            else:
                where_clauses.append("(u.nickname IS NULL OR u.nickname = '')")

        if username_search:
            like_pattern = f"%{username_search}%"
            p = _p()
            where_clauses.append(
                f"(u.username ILIKE {p}"
                f" OR u.display_name ILIKE {p}"
                f" OR u.nickname ILIKE {p})"
            )
            params.append(like_pattern)

        if followed_after:
            where_clauses.append(f"cu.followed_at >= {_p()}")
            params.append(followed_after)

        if followed_before:
            where_clauses.append(f"cu.followed_at <= {_p()}")
            params.append(followed_before)

        if unfollowed_after:
            where_clauses.append(f"cu.unfollowed_at >= {_p()}")
            params.append(unfollowed_after)

        if unfollowed_before:
            where_clauses.append(f"cu.unfollowed_at <= {_p()}")
            params.append(unfollowed_before)

        if is_follower and is_follower in ("follower", "not_follower", "unfollower"):
            if broadcaster_id:
                where_clauses.append(f"u.user_id != {_p()}")
                params.append(broadcaster_id)

            if is_follower == "follower":
                where_clauses.append(
                    "cu.followed_at IS NOT NULL AND cu.unfollowed_at IS NULL"
                )
            elif is_follower == "not_follower":
                where_clauses.append("cu.user_id IS NULL")
            elif is_follower == "unfollower":
                where_clauses.append("cu.unfollowed_at IS NOT NULL")

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sort_by_clean = (sort_by or "username").lower()
        sort_order_sql = "DESC" if (sort_order or "").lower() == "desc" else "ASC"

        if sort_by_clean == "role":
            order_by_sql = (
                "ORDER BY (CASE WHEN cu.is_moderator THEN 1 WHEN cu.is_vip THEN 2 "
                "WHEN cu.is_subscriber THEN 3 WHEN u.is_bot THEN 4 ELSE 5 END) "
                f"{sort_order_sql}, u.username ASC"
            )
        elif sort_by_clean == "follow_date":
            order_by_sql = (
                f"ORDER BY COALESCE(cu.unfollowed_at, cu.followed_at) "
                f"{sort_order_sql} NULLS LAST, u.username ASC"
            )
        else:
            order_by_sql = f"ORDER BY u.username {sort_order_sql}"

        count_query = f"""
            SELECT COUNT(*) AS total
            FROM users u
            LEFT JOIN channel_users cu ON u.user_id = cu.user_id AND cu.channel_id = $1
            {where_sql}
        """
        data_query = f"""
            SELECT u.user_id, u.username, u.display_name, u.nickname, u.is_bot,
                   COALESCE(cu.is_moderator, FALSE) as is_moderator,
                   COALESCE(cu.is_vip, FALSE) as is_vip,
                   COALESCE(cu.is_subscriber, FALSE) as is_subscriber,
                   cu.sub_tier, cu.followed_at, cu.unfollowed_at,
                   (
                       SELECT COUNT(*) FROM chat_history ch
                       WHERE ch.channel_id = $1 AND ch.user_id = u.user_id
                   ) AS message_count
            FROM users u
            LEFT JOIN channel_users cu ON u.user_id = cu.user_id AND cu.channel_id = $1
            {where_sql}
            {order_by_sql} LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """

        async with self._db.acquire() as conn:
            count_row = await conn.fetchrow(count_query, *params)
            total_count: int = count_row["total"] if count_row else 0

            rows: list[asyncpg.Record] = await conn.fetch(
                data_query, *params, limit, offset
            )

        return [dict(row) for row in rows], total_count

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

    async def search_users(
        self, q: str, limit: int = 10, channel_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Busca usuarios en la DB local para autocompletar."""
        like_pattern = f"%{q}%"
        if channel_id:
            query = """
                SELECT u.user_id, u.username, u.display_name,
                       COALESCE(u.nickname, '') AS nickname,
                       u.is_bot,
                       COALESCE(cu.is_moderator, FALSE) AS is_moderator,
                       COALESCE(cu.is_vip, FALSE) AS is_vip,
                       COALESCE(cu.is_subscriber, FALSE) AS is_subscriber,
                       (cu.user_id IS NOT NULL AND cu.unfollowed_at IS NULL)
                        AS is_follower
                FROM users u
                LEFT JOIN channel_users cu
                       ON u.user_id = cu.user_id AND cu.channel_id = $3
                WHERE u.username ILIKE $1
                   OR u.display_name ILIKE $1
                   OR u.nickname ILIKE $1
                GROUP BY u.user_id, cu.user_id, cu.unfollowed_at,
                         cu.is_moderator, cu.is_vip, cu.is_subscriber
                ORDER BY u.display_name
                LIMIT $2
            """
            async with self._db.acquire() as conn:
                rows: list[asyncpg.Record] = await conn.fetch(
                    query, like_pattern, limit, channel_id
                )
        else:
            query = """
                SELECT u.user_id, u.username, u.display_name,
                       COALESCE(u.nickname, '') AS nickname,
                       u.is_bot,
                       COALESCE(cu.is_moderator, FALSE) AS is_moderator,
                       COALESCE(cu.is_vip, FALSE) AS is_vip,
                       COALESCE(cu.is_subscriber, FALSE) AS is_subscriber,
                       (cu.user_id IS NOT NULL AND cu.unfollowed_at IS NULL)
                        AS is_follower
                FROM users u
                LEFT JOIN channel_users cu ON u.user_id = cu.user_id
                WHERE u.username ILIKE $1
                   OR u.display_name ILIKE $1
                   OR u.nickname ILIKE $1
                GROUP BY u.user_id, cu.user_id, cu.unfollowed_at,
                         cu.is_moderator, cu.is_vip, cu.is_subscriber
                ORDER BY u.display_name
                LIMIT $2
            """
            async with self._db.acquire() as conn:
                rows = await conn.fetch(query, like_pattern, limit)
        return [dict(row) for row in rows]

    async def get_profile_image_url(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve la URL del avatar cacheada, o None si no existe."""
        if cache is not None:
            url = cache.get_profile_image_url(user_id)
            if url is not None:
                return url
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT profile_image_url FROM users WHERE user_id = $1",
                user_id,
            )
        if not row:
            return None
        return row["profile_image_url"]

    async def set_profile_image_url(
        self, user_id: str, url: str, cache: UserMemoryCache | None = None
    ) -> None:
        """Guarda o actualiza la URL del avatar del usuario."""
        if cache is not None:
            cache.set_profile_image_url(user_id, url)
        LOGGER.debug("DB UPDATE avatar para user_id %s en PostgreSQL", user_id)

        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET profile_image_url = $1 WHERE user_id = $2",
                url,
                user_id,
            )

    async def _fetch_message_counts_batch(
        self, channel_id: str, user_ids: list[str]
    ) -> dict[str, int]:
        """Retorna {user_id: message_count} para un lote de user_ids en un canal."""
        if not user_ids:
            return {}
        query = """
            SELECT user_id, COUNT(*) AS total
            FROM chat_history
            WHERE channel_id = $1 AND user_id = ANY($2)
            GROUP BY user_id
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, user_ids)
        return {row["user_id"]: int(row["total"]) for row in rows}
