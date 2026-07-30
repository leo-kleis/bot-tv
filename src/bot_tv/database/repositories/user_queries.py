from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class UserQueriesMixin(BaseRepository):
    """Búsquedas, filtrado avanzado y agrupaciones sobre usuarios."""

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

    async def list_users_with_filters(
        self,
        channel_id: str,
        broadcaster_id: str | None = None,
        role: str | None = None,
        has_nickname: bool | None = None,
        has_chat_history: bool | None = None,
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
        if cache is not None and has_chat_history is None:
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

        if has_chat_history is not None:
            if has_chat_history:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM chat_history ch "
                    "WHERE ch.channel_id = $1 AND ch.user_id = u.user_id)"
                )
            else:
                where_clauses.append(
                    "NOT EXISTS (SELECT 1 FROM chat_history ch "
                    "WHERE ch.channel_id = $1 AND ch.user_id = u.user_id)"
                )

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
