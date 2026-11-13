from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

import asyncpg

from bot_tv.database.repositories.base import (
    BaseRepository,
    escape_like,
    to_iso_str,
    to_utc_datetime,
)

LOGGER = logging.getLogger(__name__)

BATCH_FLUSH_INTERVAL = 2.0
MAX_BATCH_SIZE = 20
MAX_QUEUE_SIZE = 2000


class ChatRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla chat_history."""

    def __init__(self, db: asyncpg.Pool) -> None:
        super().__init__(db)
        self._msg_queue: deque[tuple[str, str, str, str, datetime, str | None]] = deque(
            maxlen=MAX_QUEUE_SIZE
        )
        self._batch_task: asyncio.Task[None] | None = None
        self._flush_task: asyncio.Task[None] | None = None
        self._flush_lock = asyncio.Lock()
        self._closed = False

    def start_batch_worker(self) -> None:
        """Inicia el worker en segundo plano si no está corriendo."""
        if self._closed:
            return
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._batch_loop())

    async def _batch_loop(self) -> None:
        """Bucle periódico para hacer flush de la cola de chat."""
        while not self._closed:
            await asyncio.sleep(BATCH_FLUSH_INTERVAL)
            if self._closed:
                break
            await self.flush()

    async def _drain_batches(self) -> None:
        """Drena lotes completos sin crear tareas concurrentes de flush."""
        try:
            while not self._closed and len(self._msg_queue) >= MAX_BATCH_SIZE:
                if not await self._flush_locked():
                    break
        finally:
            if asyncio.current_task() is self._flush_task:
                self._flush_task = None

    def _requeue_preserving_newest(
        self,
        batch: list[tuple[str, str, str, str, datetime, str | None]],
    ) -> None:
        """Re-encola mensajes fallidos sin expulsar los mensajes más recientes."""
        available = MAX_QUEUE_SIZE - len(self._msg_queue)
        if available <= 0:
            LOGGER.warning(
                "Cola chat_history llena (%d); descartando %d mensajes antiguos.",
                MAX_QUEUE_SIZE,
                len(batch),
            )
            return
        if available < len(batch):
            dropped = len(batch) - available
            LOGGER.warning(
                "Cola chat_history cerca del límite; descartando %d mensajes antiguos "
                "para preservar los más recientes.",
                dropped,
            )
            batch = batch[-available:]
        self._msg_queue.extendleft(reversed(batch))

    async def save_chat_message(
        self,
        channel_id: str,
        user_id: str,
        message: str,
        msg_id: str | None = None,
        stream_id: str | None = None,
    ) -> None:
        """Encola un mensaje para su guardado en lote en chat_history."""
        if self._closed:
            LOGGER.warning(
                "Mensaje descartado: ChatRepository ya fue cerrado (channel_id=%s).",
                channel_id,
            )
            return
        if not msg_id:
            msg_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        self._msg_queue.append((msg_id, channel_id, user_id, message, now, stream_id))
        self.start_batch_worker()

        if len(self._msg_queue) >= MAX_BATCH_SIZE and (
            self._flush_task is None or self._flush_task.done()
        ):
            self._flush_task = asyncio.create_task(self._drain_batches())

    async def flush(self) -> None:
        """Escribe todos los mensajes acumulados en la cola a PostgreSQL."""
        await self._flush_locked()

    async def _flush_locked(self) -> bool:
        """Ejecuta el flush serializado; False ante fallo transitorio."""
        async with self._flush_lock:
            if not self._msg_queue:
                return True

            to_insert = list(self._msg_queue)
            self._msg_queue.clear()

            ids: list[uuid.UUID] = []
            channel_ids: list[str] = []
            user_ids: list[str] = []
            messages: list[str] = []
            timestamps: list[datetime] = []
            stream_ids: list[str | None] = []
            valid_entries: list[tuple[str, str, str, str, datetime, str | None]] = []

            for entry in to_insert:
                raw_id, channel_id, user_id, message, ts, stream_id = entry
                try:
                    parsed_id = uuid.UUID(raw_id)
                except ValueError, TypeError:
                    LOGGER.error(
                        "Mensaje descartado en chat_history por UUID inválido: %r",
                        raw_id,
                    )
                    continue
                ids.append(parsed_id)
                channel_ids.append(channel_id)
                user_ids.append(user_id)
                messages.append(message)
                timestamps.append(ts)
                stream_ids.append(stream_id)
                valid_entries.append(entry)

            if not ids:
                return True

            try:
                query = """
                    INSERT INTO chat_history (
                        id, channel_id, user_id, message, timestamp, stream_id
                    )
                    SELECT * FROM UNNEST(
                        $1::uuid[],
                        $2::text[],
                        $3::text[],
                        $4::text[],
                        $5::timestamptz[],
                        $6::text[]
                    )
                    ON CONFLICT (id) DO NOTHING
                """
                await self._execute(
                    query,
                    ids,
                    channel_ids,
                    user_ids,
                    messages,
                    timestamps,
                    stream_ids,
                    context_label="flush chat_history",
                )
                LOGGER.debug(
                    "DB BATCH INSERT chat_history: %d mensajes guardados",
                    len(ids),
                )
                return True
            except (
                asyncpg.IntegrityConstraintViolationError,
                asyncpg.DataError,
            ) as exc:
                LOGGER.error(
                    "Lote descartado en chat_history por error de datos/integridad: %s",
                    exc,
                )
                return True
            except Exception as exc:
                LOGGER.exception(
                    "Error al hacer batch insert en chat_history: %s",
                    exc,
                )
                self._requeue_preserving_newest(valid_entries)
                return False

    async def close(self) -> None:
        """Cancela el worker y vacía los mensajes pendientes de forma idempotente."""
        if self._closed:
            return
        self._closed = True

        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._batch_task
        self._batch_task = None

        if self._flush_task and not self._flush_task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        self._flush_task = None

        await self.flush()

    async def get_message_count_in_range(
        self,
        channel_id: str,
        start_time: datetime | str,
        end_time: datetime | str,
    ) -> int:
        """Devuelve el total de mensajes en un canal para un rango de tiempo dado."""
        dt_start = to_utc_datetime(start_time)
        dt_end = to_utc_datetime(end_time)
        query = """
            SELECT COUNT(*) as msg_count
            FROM chat_history
            WHERE channel_id = $1 AND timestamp >= $2 AND timestamp <= $3
        """
        row = await self._fetchrow(
            query,
            channel_id,
            dt_start,
            dt_end,
            context_label="get_message_count_in_range",
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
        row = await self._fetchrow(query, channel_id, context_label="get_chat_stats")
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
            WITH top_senders AS (
                SELECT user_id, COUNT(*) AS msg_count
                FROM chat_history
                WHERE channel_id = $1
                GROUP BY user_id
                ORDER BY msg_count DESC
                LIMIT $2
            )
            SELECT u.username, u.display_name, u.nickname, ts.msg_count
            FROM top_senders ts
            JOIN users u ON ts.user_id = u.user_id
            ORDER BY ts.msg_count DESC
        """
        rows = await self._fetch(
            query, channel_id, limit, context_label="get_top_chatters"
        )
        return [dict(row) for row in rows]

    async def get_messages_with_filters(
        self,
        channel_id: str,
        username: str | None = None,
        role: str | None = None,
        search_term: str | None = None,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Devuelve los mensajes de chat aplicando diversos filtros dinámicos."""
        where_clauses = ["c.channel_id = $1"]
        params: list[Any] = [channel_id]

        def _p() -> str:
            return f"${len(params) + 1}"

        dt_since = to_utc_datetime(since)
        if dt_since is not None:
            where_clauses.append(f"c.timestamp >= {_p()}")
            params.append(dt_since)

        dt_until = to_utc_datetime(until)
        if dt_until is not None:
            where_clauses.append(f"c.timestamp <= {_p()}")
            params.append(dt_until)

        if username:
            where_clauses.append(f"LOWER(u.username) = LOWER({_p()})")
            params.append(username)

        if search_term:
            where_clauses.append(f"c.message ILIKE {_p()} ESCAPE '\\'")
            params.append(f"%{escape_like(search_term)}%")

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

        query = f"""
            SELECT u.username, u.display_name, u.nickname, c.message, c.timestamp
            FROM chat_history c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN channel_users cu
                   ON c.user_id = cu.user_id AND c.channel_id = cu.channel_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY c.timestamp DESC LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """  # noqa: S608

        params.append(limit)
        params.append(offset)

        rows = await self._fetch(
            query, *params, context_label="get_messages_with_filters"
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["timestamp"] = to_iso_str(item.get("timestamp"))
            results.append(item)
        return results

    async def get_user_message_count(
        self,
        channel_id: str,
        user_id: str,
        search_term: str | None = None,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
    ) -> int:
        """Devuelve el total de mensajes de un usuario en un canal (con filtros)."""
        if not user_id:
            return 0

        where_clauses = ["channel_id = $1", "user_id = $2"]
        params: list[Any] = [channel_id, user_id]

        def _p() -> str:
            return f"${len(params) + 1}"

        dt_since = to_utc_datetime(since)
        if dt_since is not None:
            where_clauses.append(f"timestamp >= {_p()}")
            params.append(dt_since)

        dt_until = to_utc_datetime(until)
        if dt_until is not None:
            where_clauses.append(f"timestamp <= {_p()}")
            params.append(dt_until)

        if search_term:
            where_clauses.append(f"message ILIKE {_p()} ESCAPE '\\'")
            params.append(f"%{escape_like(search_term)}%")

        query = f"""
            SELECT COUNT(*) AS total
            FROM chat_history
            WHERE {" AND ".join(where_clauses)}
        """  # noqa: S608
        row = await self._fetchrow(
            query, *params, context_label="get_user_message_count"
        )
        return int(row["total"]) if row else 0
