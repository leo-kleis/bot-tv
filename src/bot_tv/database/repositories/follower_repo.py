from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository


class FollowerRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla followers."""

    async def get_follower_ids(self, channel_id: str) -> set[str]:
        """Devuelve el conjunto de user_id que siguen a un canal."""
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                "SELECT user_id FROM followers "
                "WHERE channel_id = $1 AND unfollowed_at IS NULL",
                channel_id,
            )
        return {row["user_id"] for row in rows}

    async def sync_followers(
        self,
        channel_id: str,
        new_followers: list[tuple[str, str, str | None]],
        unfollowed_ids: list[str] | None = None,
    ) -> None:
        """Sincroniza solo las diferencias con la DB usando batch operations.

        new_followers: seguidores NUEVOS que no estaban en la DB.
        unfollowed_ids: IDs que dejaron de seguir desde la última sync.
        """
        if not new_followers and not unfollowed_ids:
            return

        now_iso = datetime.now(UTC).isoformat()

        async with self._db.acquire() as conn:
            # Batch: marcar unfollows
            if unfollowed_ids:
                await conn.executemany(
                    "UPDATE followers SET unfollowed_at = $1 "
                    "WHERE channel_id = $2 AND user_id = $3",
                    [(now_iso, channel_id, uid) for uid in unfollowed_ids],
                )

            # Batch: upsert users + followers solo para los nuevos
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
                    INSERT INTO followers (
                        channel_id, user_id, followed_at, unfollowed_at
                    )
                    VALUES ($1, $2, $3, NULL)
                    ON CONFLICT (channel_id, user_id) DO UPDATE SET
                        followed_at   = EXCLUDED.followed_at,
                        unfollowed_at = NULL
                    """,
                    [
                        (channel_id, uid, fat)
                        for uid, _, fat in new_followers
                    ],
                )


    async def get_follower_stats(self, channel_id: str) -> dict[str, int] | None:
        """Devuelve las estadísticas generales de seguidores para un canal."""
        query = """
            SELECT COUNT(*) as total_records,
                   SUM(CASE WHEN unfollowed_at IS NULL
                            THEN 1 ELSE 0 END) as active_followers,
                   SUM(CASE WHEN unfollowed_at IS NOT NULL
                            THEN 1 ELSE 0 END) as unfollowers
            FROM followers
            WHERE channel_id = $1
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
                   f.followed_at, f.unfollowed_at
            FROM followers f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.channel_id = $1 AND (
                u.username ILIKE $2 OR
                u.display_name ILIKE $2 OR
                u.nickname ILIKE $2
            )
        """
        if active_only:
            query += " AND f.unfollowed_at IS NULL"
        query += " ORDER BY f.followed_at DESC LIMIT $3"

        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                query, channel_id, like_pattern, limit
            )
        return [dict(row) for row in rows]

    async def get_recent_followers(
        self, channel_id: str, limit: int = 5, active_only: bool = False
    ) -> list[dict[str, Any]]:
        """Obtiene la lista de los seguidores registrados más recientemente."""
        limit = max(1, limit)
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   f.followed_at, f.unfollowed_at
            FROM followers f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.channel_id = $1
        """
        if active_only:
            query += " AND f.unfollowed_at IS NULL"
        query += " ORDER BY f.followed_at DESC LIMIT $2"

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
                   f.followed_at, f.unfollowed_at
            FROM followers f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.channel_id = $1 AND f.unfollowed_at IS NOT NULL
            ORDER BY f.unfollowed_at DESC LIMIT $2
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, limit)
        return [dict(row) for row in rows]
