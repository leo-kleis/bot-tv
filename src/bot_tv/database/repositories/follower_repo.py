from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    import sqlite3


class FollowerRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla followers."""

    async def get_follower_ids(self, channel_id: str) -> set[str]:
        """Devuelve el conjunto de user_id que siguen a un canal."""
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(
                "SELECT user_id FROM followers "
                "WHERE channel_id = ? AND unfollowed_at IS NULL",
                (channel_id,),
            )
        return {row["user_id"] for row in rows}

    async def sync_followers(
        self,
        channel_id: str,
        followers: list[tuple[str, str, str | None]],
        unfollowed_ids: list[str] | None = None,
    ) -> None:
        """Actualiza los seguidores de un canal marcando los que dejaron de seguir."""
        if unfollowed_ids is None:
            unfollowed_ids = []

        now_iso = datetime.now(UTC).isoformat()

        async with self._db.acquire() as conn:
            # Marcar los que dejaron de seguir
            for uid in unfollowed_ids:
                await conn.execute(
                    "UPDATE followers SET unfollowed_at = ? "
                    "WHERE channel_id = ? AND user_id = ?",
                    (now_iso, channel_id, uid),
                )

            # Insertar o actualizar los seguidores actuales
            for user_id, username, followed_at in followers:
                # Asegurar que el usuario existe en la tabla users
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                    WHERE users.username IS NOT excluded.username
                    """,
                    (user_id, username),
                )
                await conn.execute(
                    """
                    INSERT INTO followers (
                        channel_id, user_id, followed_at, unfollowed_at
                    )
                    VALUES (?, ?, ?, NULL)
                    ON CONFLICT(channel_id, user_id) DO UPDATE SET 
                        followed_at = excluded.followed_at,
                        unfollowed_at = NULL
                    WHERE
                        followers.followed_at IS NOT excluded.followed_at OR
                        followers.unfollowed_at IS NOT NULL
                    """,
                    (channel_id, user_id, followed_at),
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
            WHERE channel_id = ?
        """
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(query, (channel_id,))
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
        query = """
            SELECT u.username, u.display_name, u.nickname,
                   f.followed_at, f.unfollowed_at
            FROM followers f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.channel_id = ? AND (
                u.username LIKE ? OR 
                u.display_name LIKE ? OR 
                u.nickname LIKE ?
            )
        """
        if active_only:
            query += " AND f.unfollowed_at IS NULL"
        query += " ORDER BY f.followed_at DESC LIMIT ?"

        like_pattern = f"%{search_term}%"
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(
                query, (channel_id, like_pattern, like_pattern, like_pattern, limit)
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
            WHERE f.channel_id = ?
        """
        if active_only:
            query += " AND f.unfollowed_at IS NULL"
        query += " ORDER BY f.followed_at DESC LIMIT ?"

        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(query, (channel_id, limit))
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
            WHERE f.channel_id = ? AND f.unfollowed_at IS NOT NULL
            ORDER BY f.unfollowed_at DESC LIMIT ?
        """
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(query, (channel_id, limit))
        return [dict(row) for row in rows]
