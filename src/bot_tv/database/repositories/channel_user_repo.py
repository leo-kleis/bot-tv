from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import (
    BaseRepository,
    escape_like,
    to_iso_str,
    to_utc_datetime,
)

if TYPE_CHECKING:
    import asyncpg

    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class ChannelUserRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla channel_users
    (seguidores y roles por canal).
    """

    async def get_follower_ids(
        self, channel_id: str, cache: UserMemoryCache | None = None
    ) -> set[str]:
        """Devuelve el conjunto de user_id que siguen a un canal."""
        if cache is not None and cache.has_users:
            return cache.get_follower_ids(channel_id)
        rows = await self._fetch(
            "SELECT user_id FROM channel_users "
            "WHERE channel_id = $1 "
            "AND followed_at IS NOT NULL AND unfollowed_at IS NULL",
            channel_id,
            context_label="get_follower_ids",
        )
        return {row["user_id"] for row in rows}

    async def set_user_follow_status(
        self,
        channel_id: str,
        user_id: str,
        followed_at: datetime | str | None,
        *,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Actualiza el estado de follow individual de un usuario en DB y caché."""
        dt_followed = to_utc_datetime(followed_at)
        iso_followed = to_iso_str(followed_at)

        query = """
            INSERT INTO channel_users (
                channel_id, user_id, followed_at, unfollowed_at
            )
            VALUES ($1, $2, $3, NULL)
            ON CONFLICT (channel_id, user_id) DO UPDATE SET
                followed_at = EXCLUDED.followed_at,
                unfollowed_at = NULL
        """
        await self._execute(
            query,
            channel_id,
            user_id,
            dt_followed,
            context_label="set_user_follow_status",
        )

        if cache is not None:
            cache.set_user_follow_status(channel_id, user_id, iso_followed)

    async def sync_followers(
        self,
        channel_id: str,
        new_followers: list[tuple[str, str, str | None]],
        unfollowed_ids: list[str] | None = None,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Sincroniza solo las diferencias con la DB usando batch operations.

        new_followers: seguidores NUEVOS que no estaban en la DB.
        unfollowed_ids: IDs que dejaron de seguir desde la última sync.
        """
        if not new_followers and not unfollowed_ids:
            return

        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()
        deduped_unfollows = (
            list(dict.fromkeys(unfollowed_ids)) if unfollowed_ids else []
        )

        # Deduplicar por user_id para evitar CardinalityViolationError en UNNEST+UPSERT.
        deduped_followers: dict[str, tuple[str, datetime | None]] = {}
        for uid, uname, fat in new_followers:
            deduped_followers[uid] = (uname, to_utc_datetime(fat))

        new_uids = list(deduped_followers.keys())
        new_usernames = [uname for uname, _ in deduped_followers.values()]
        new_followed_ats = [fat for _, fat in deduped_followers.values()]

        LOGGER.info(
            "DB BATCH UPDATE seguidores canal %s: %d nuevos, %d unfollows",
            channel_id,
            len(new_uids),
            len(deduped_unfollows),
        )

        async def _apply_sync(conn: asyncpg.Connection) -> None:
            if deduped_unfollows:
                await conn.execute(
                    """
                    UPDATE channel_users AS cu
                    SET unfollowed_at = $1
                    FROM UNNEST($3::text[]) AS batch(user_id)
                    WHERE cu.channel_id = $2 AND cu.user_id = batch.user_id
                    """,
                    now_dt,
                    channel_id,
                    deduped_unfollows,
                )

            if new_uids:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username)
                    SELECT * FROM UNNEST($1::text[], $2::text[])
                    ON CONFLICT (user_id)
                    DO UPDATE SET username = EXCLUDED.username
                    WHERE users.username IS DISTINCT FROM EXCLUDED.username
                    """,
                    new_uids,
                    new_usernames,
                )
                await conn.execute(
                    """
                    INSERT INTO channel_users (
                        channel_id, user_id, followed_at, unfollowed_at
                    )
                    SELECT $1, batch.user_id, batch.followed_at, NULL
                    FROM UNNEST($2::text[], $3::timestamptz[])
                        AS batch(user_id, followed_at)
                    ON CONFLICT (channel_id, user_id) DO UPDATE SET
                        followed_at   = EXCLUDED.followed_at,
                        unfollowed_at = NULL
                    """,
                    channel_id,
                    new_uids,
                    new_followed_ats,
                )

        await self._with_transaction(_apply_sync, context_label="sync_followers")

        if cache is not None:
            cache.sync_followers(
                channel_id, new_followers, deduped_unfollows or None, now_iso
            )

    async def get_follower_stats(self, channel_id: str) -> dict[str, int] | None:
        """Devuelve las estadísticas de seguidores (excluyendo bots)."""
        query = """
            SELECT COUNT(*) as total_records,
                   SUM(CASE WHEN cu.unfollowed_at IS NULL
                            THEN 1 ELSE 0 END) as active_followers,
                   SUM(CASE WHEN cu.unfollowed_at IS NOT NULL
                            THEN 1 ELSE 0 END) as unfollowers
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND u.is_bot = FALSE
        """
        row = await self._fetchrow(
            query, channel_id, context_label="get_follower_stats"
        )
        if not row or row["total_records"] == 0:
            return None
        return {
            "total_records": row["total_records"] or 0,
            "active_followers": row["active_followers"] or 0,
            "unfollowers": row["unfollowers"] or 0,
        }

    async def search_followers(
        self,
        channel_id: str,
        search_term: str,
        active_only: bool = False,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Busca seguidores en base a un término de búsqueda (coincidencia en users)."""
        limit = max(1, min(limit, 100))
        like_pattern = f"%{escape_like(search_term)}%"
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   cu.followed_at, cu.unfollowed_at
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND u.is_bot = FALSE AND (
                u.username ILIKE $2 ESCAPE '\\' OR
                u.display_name ILIKE $2 ESCAPE '\\' OR
                u.nickname ILIKE $2 ESCAPE '\\'
            )
        """
        if active_only:
            query += " AND cu.unfollowed_at IS NULL"
        query += " ORDER BY cu.followed_at DESC NULLS LAST LIMIT $3"

        rows = await self._fetch(
            query,
            channel_id,
            like_pattern,
            limit,
            context_label="search_followers",
        )
        return [
            {
                **dict(row),
                "followed_at": to_iso_str(row["followed_at"]),
                "unfollowed_at": to_iso_str(row["unfollowed_at"]),
            }
            for row in rows
        ]

    async def get_recent_followers(
        self, channel_id: str, limit: int = 5, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Obtiene los seguidores más recientes (activos por defecto)."""
        limit = max(1, min(limit, 100))
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   cu.followed_at, cu.unfollowed_at
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND u.is_bot = FALSE
        """
        if active_only:
            query += " AND cu.unfollowed_at IS NULL"
        query += " ORDER BY cu.followed_at DESC NULLS LAST LIMIT $2"

        rows = await self._fetch(
            query, channel_id, limit, context_label="get_recent_followers"
        )
        return [
            {
                **dict(row),
                "followed_at": to_iso_str(row["followed_at"]),
                "unfollowed_at": to_iso_str(row["unfollowed_at"]),
            }
            for row in rows
        ]

    async def get_recent_unfollowers(
        self, channel_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Obtiene la lista de los usuarios que han dejado de seguir el canal."""
        limit = max(1, min(limit, 100))
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   cu.followed_at, cu.unfollowed_at
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND cu.unfollowed_at IS NOT NULL
            ORDER BY cu.unfollowed_at DESC LIMIT $2
        """
        rows = await self._fetch(
            query, channel_id, limit, context_label="get_recent_unfollowers"
        )
        return [
            {
                **dict(row),
                "followed_at": to_iso_str(row["followed_at"]),
                "unfollowed_at": to_iso_str(row["unfollowed_at"]),
            }
            for row in rows
        ]

    async def upsert_channel_user_roles(
        self,
        channel_id: str,
        user_id: str,
        is_moderator: bool,
        is_vip: bool,
        is_subscriber: bool,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Registra o actualiza los roles específicos del canal para un usuario."""
        if cache is not None and not cache.needs_roles_update(
            channel_id, user_id, is_moderator, is_vip, is_subscriber
        ):
            return

        query = """
            INSERT INTO channel_users (
                channel_id, user_id, is_moderator, is_vip, is_subscriber
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (channel_id, user_id)
            DO UPDATE SET is_moderator = EXCLUDED.is_moderator,
                          is_vip = EXCLUDED.is_vip,
                          is_subscriber = EXCLUDED.is_subscriber
        """
        await self._execute(
            query,
            channel_id,
            user_id,
            is_moderator,
            is_vip,
            is_subscriber,
            context_label="upsert_channel_user_roles",
        )

        if cache is not None:
            cache.update_roles(channel_id, user_id, is_moderator, is_vip, is_subscriber)
