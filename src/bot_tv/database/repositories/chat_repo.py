import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

LOGGER = logging.getLogger(__name__)

BATCH_FLUSH_INTERVAL = 2.0
MAX_BATCH_SIZE = 20


class ChatRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla chat_history."""

    def __init__(self, db: asyncpg.Pool) -> None:
        super().__init__(db)
        self._msg_queue: list[tuple[str, str, str, str]] = []
        self._batch_task: asyncio.Task[None] | None = None
        self._flush_lock = asyncio.Lock()

    def start_batch_worker(self) -> None:
        """Inicia el worker en segundo plano si no está corriendo."""
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._batch_loop())

    async def _batch_loop(self) -> None:
        """Bucle periódico para hacer flush de la cola de chat."""
        while True:
            await asyncio.sleep(BATCH_FLUSH_INTERVAL)
            await self.flush()

    async def save_chat_message(
        self,
        channel_id: str,
        user_id: str,
        message: str,
    ) -> None:
        """Encola un mensaje para su guardado en lote en chat_history."""
        now = datetime.now(UTC).isoformat()
        self._msg_queue.append((channel_id, user_id, message, now))
        self.start_batch_worker()

        if len(self._msg_queue) >= MAX_BATCH_SIZE:
            task = asyncio.create_task(self.flush())
            task.add_done_callback(lambda _: None)

    async def flush(self) -> None:
        """Escribe todos los mensajes acumulados en la cola a PostgreSQL."""
        async with self._flush_lock:
            if not self._msg_queue:
                return

            to_insert = self._msg_queue.copy()
            self._msg_queue.clear()

            try:
                query = """
                    INSERT INTO chat_history (channel_id, user_id, message, timestamp)
                    VALUES ($1, $2, $3, $4)
                """
                async with self._db.acquire() as conn:
                    await conn.executemany(query, to_insert)
                LOGGER.info(
                    "DB BATCH INSERT chat_history: %d mensajes guardados",
                    len(to_insert),
                )

            except Exception as e:
                LOGGER.exception("Error al hacer batch insert en chat_history: %s", e)

                # Re-encolar si falla la transacción
                self._msg_queue.extend(to_insert)

    async def close(self) -> None:
        """Cancela el worker y vacía los mensajes pendientes."""
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._batch_task
        await self.flush()

    async def get_message_count_in_range(
        self, channel_id: str, start_time: str, end_time: str
    ) -> int:
        """Devuelve el total de mensajes en un canal para un rango de tiempo dado."""
        query = """
            SELECT COUNT(*) as msg_count
            FROM chat_history
            WHERE channel_id = $1 AND timestamp >= $2 AND timestamp <= $3
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                query, channel_id, start_time, end_time
            )
        return row["msg_count"] if row else 0

    async def get_chat_stats(self, channel_id: str) -> dict[str, int] | None:
        """Devuelve estadísticas generales de mensajes y usuarios para un canal."""
        query = """
            SELECT COUNT(*) as total_messages,
                   COUNT(DISTINCT user_id) as unique_users
            FROM chat_history
            WHERE channel_id = $1
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(query, channel_id)
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
            WHERE c.channel_id = $1
            GROUP BY c.user_id, u.username, u.display_name, u.nickname
            ORDER BY msg_count DESC LIMIT $2
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, limit)
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
        where_clauses = ["c.channel_id = $1"]
        params: list[Any] = [channel_id]

        def _p() -> str:
            return f"${len(params) + 1}"

        if since:
            where_clauses.append(f"c.timestamp >= {_p()}")
            params.append(since)

        if until:
            where_clauses.append(f"c.timestamp <= {_p()}")
            params.append(until)

        if username:
            where_clauses.append(f"u.username ILIKE {_p()}")
            params.append(username)

        if search_term:
            where_clauses.append(f"c.message ILIKE {_p()}")
            params.append(f"%{search_term}%")

        if role:
            role_clean = role.lower()
            if role_clean in ("bot", "bots"):
                where_clauses.append("u.is_bot = TRUE")
            elif role_clean in ("moderator", "moderador", "mods", "mod"):
                where_clauses.append("u.is_moderator = TRUE")
            elif role_clean in ("vip", "vips"):
                where_clauses.append("u.is_vip = TRUE")
            elif role_clean in (
                "subscriber",
                "suscriptor",
                "subscribers",
                "sub",
                "subs",
            ):
                where_clauses.append("u.is_subscriber = TRUE")

        query = f"""
            SELECT u.username, u.display_name, u.nickname, c.message, c.timestamp
            FROM chat_history c
            JOIN users u ON c.user_id = u.user_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY c.timestamp DESC LIMIT ${len(params) + 1}
        """
        params.append(limit)

        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, *params)
        return [dict(row) for row in rows]
