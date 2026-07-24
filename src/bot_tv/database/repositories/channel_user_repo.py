import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
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
        if cache is not None:
            return cache.get_follower_ids(channel_id)
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                "SELECT user_id FROM channel_users "
                "WHERE channel_id = $1 "
                "AND followed_at IS NOT NULL AND unfollowed_at IS NULL",
                channel_id,
            )
        return {row["user_id"] for row in rows}

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

        now_iso = datetime.now(UTC).isoformat()
        if cache is not None:
            cache.sync_followers(channel_id, new_followers, unfollowed_ids, now_iso)

        LOGGER.info(
            "DB BATCH UPDATE seguidores canal %s: %d nuevos, %d unfollows",
            channel_id,
            len(new_followers),
            len(unfollowed_ids or []),
        )

        async with self._db.acquire() as conn:
            # Batch: marcar unfollows
            if unfollowed_ids:
                await conn.executemany(
                    "UPDATE channel_users SET unfollowed_at = $1 "
                    "WHERE channel_id = $2 AND user_id = $3",
                    [(now_iso, channel_id, uid) for uid in unfollowed_ids],
                )

            # Batch: upsert users + channel_users solo para los nuevos
            if new_followers:
                await conn.executemany(
                    """
                    INSERT INTO users (user_id, username)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id)
                    DO UPDATE SET username = EXCLUDED.username
                    WHERE users.username IS DISTINCT FROM EXCLUDED.username
                    """,
                    [(uid, uname) for uid, uname, _ in new_followers],
                )
                await conn.executemany(
                    """
                    INSERT INTO channel_users (
                        channel_id, user_id, followed_at, unfollowed_at
                    )
                    VALUES ($1, $2, $3, NULL)
                    ON CONFLICT (channel_id, user_id) DO UPDATE SET
                        followed_at   = EXCLUDED.followed_at,
                        unfollowed_at = NULL
                    """,
                    [(channel_id, uid, fat) for uid, _, fat in new_followers],
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
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(query, channel_id)
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
        limit = max(1, limit)
        like_pattern = f"%{search_term}%"
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   cu.followed_at, cu.unfollowed_at
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND u.is_bot = FALSE AND (
                u.username ILIKE $2 OR
                u.display_name ILIKE $2 OR
                u.nickname ILIKE $2
            )
        """
        if active_only:
            query += " AND cu.unfollowed_at IS NULL"
        query += " ORDER BY cu.followed_at DESC NULLS LAST LIMIT $3"

        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                query, channel_id, like_pattern, limit
            )
        return [dict(row) for row in rows]

    async def get_recent_followers(
        self, channel_id: str, limit: int = 5, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Obtiene los seguidores más recientes (activos por defecto)."""

        limit = max(1, limit)
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

        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, limit)
        return [dict(row) for row in rows]

    async def get_recent_unfollowers(
        self, channel_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Obtiene la lista de los usuarios que han dejado de seguir el canal."""
        limit = max(1, limit)
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   cu.followed_at, cu.unfollowed_at
            FROM channel_users cu
            JOIN users u ON cu.user_id = u.user_id
            WHERE cu.channel_id = $1 AND cu.unfollowed_at IS NOT NULL
            ORDER BY cu.unfollowed_at DESC LIMIT $2
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, limit)
        return [dict(row) for row in rows]

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
        if cache is not None:
            if not cache.needs_roles_update(
                channel_id, user_id, is_moderator, is_vip, is_subscriber
            ):
                return
            cache.update_roles(channel_id, user_id, is_moderator, is_vip, is_subscriber)

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
        async with self._db.acquire() as conn:
            await conn.execute(
                query, channel_id, user_id, is_moderator, is_vip, is_subscriber
            )
