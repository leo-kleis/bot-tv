from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    import sqlite3


class ChatRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla chat_history."""

    async def save_chat_message(
        self,
        channel_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Guarda un mensaje en el historial de chat."""
        now = datetime.now(UTC).isoformat()
        query = """
            INSERT INTO chat_history (channel_id, user_id, message, timestamp)
            VALUES (?, ?, ?, ?)
        """
        async with self._db.acquire() as conn:
            await conn.execute(query, (channel_id, user_id, message, now))

    async def get_message_count_in_range(
        self, channel_id: str, start_time: str, end_time: str
    ) -> int:
        """Devuelve el total de mensajes en un canal para un rango de tiempo dado."""
        query = """
            SELECT COUNT(*) as msg_count
            FROM chat_history
            WHERE channel_id = ? AND timestamp >= ? AND timestamp <= ?
        """
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(
                query, (channel_id, start_time, end_time)
            )
        return row["msg_count"] if row else 0

    async def get_chat_stats(self, channel_id: str) -> dict[str, int] | None:
        """Devuelve estadísticas generales de mensajes y usuarios para un canal."""
        query = """
            SELECT COUNT(*) as total_messages,
                   COUNT(DISTINCT user_id) as unique_users
            FROM chat_history
            WHERE channel_id = ?
        """
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(query, (channel_id,))
        if not row:
            return None
        return {
            "total_messages": row["total_messages"] or 0,
            "unique_users": row["unique_users"] or 0,
        }

    async def get_top_chatters(
        self, channel_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Devuelve los usuarios con mayor cantidad de mensajes enviados."""
        query = """
            SELECT u.username, u.display_name, u.nickname, COUNT(c.id) as msg_count
            FROM chat_history c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.channel_id = ?
            GROUP BY c.user_id
            ORDER BY msg_count DESC LIMIT ?
        """
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(query, (channel_id, limit))
        return [dict(row) for row in rows]

    async def get_messages_with_filters(
        self,
        channel_id: str,
        username: str | None = None,
        role: str | None = None,
        search_term: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Devuelve los mensajes de chat aplicando diversos filtros dinámicos."""
        where_clauses = ["c.channel_id = ?"]
        params: list[Any] = [channel_id]

        if since:
            where_clauses.append("c.timestamp >= ?")
            params.append(since)

        if until:
            where_clauses.append("c.timestamp <= ?")
            params.append(until)

        if username:
            where_clauses.append("u.username = ? COLLATE NOCASE")
            params.append(username)

        if search_term:
            where_clauses.append("c.message LIKE ?")
            params.append(f"%{search_term}%")

        if role:
            role_clean = role.lower()
            if role_clean in ("bot", "bots"):
                where_clauses.append("u.is_bot = 1")
            elif role_clean in ("moderator", "moderador", "mods", "mod"):
                where_clauses.append("u.is_moderator = 1")
            elif role_clean in ("vip", "vips"):
                where_clauses.append("u.is_vip = 1")
            elif role_clean in (
                "subscriber",
                "suscriptor",
                "subscribers",
                "sub",
                "subs",
            ):
                where_clauses.append("u.is_subscriber = 1")

        query = f"""  # noqa: S608
            SELECT u.username, u.display_name, u.nickname, c.message, c.timestamp
            FROM chat_history c
            JOIN users u ON c.user_id = u.user_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY c.timestamp DESC LIMIT ?
        """
        params.append(limit)

        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(query, tuple(params))
        return [dict(row) for row in rows]
