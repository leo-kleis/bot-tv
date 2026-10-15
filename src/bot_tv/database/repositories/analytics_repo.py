from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

LOGGER = logging.getLogger(__name__)


class AnalyticsRepository(BaseRepository):
    """Repositorio para gestionar analíticas, telemetría y ciclo de vida de streams."""

    async def create_or_get_session(
        self,
        channel_id: str,
        stream_id: str,
        started_at: datetime | str,
        title: str | None = None,
        category_name: str | None = None,
    ) -> dict[str, Any]:
        """Crea o actualiza una sesión de transmisión activa en stream_sessions."""
        if isinstance(started_at, str):
            dt_started = datetime.fromisoformat(started_at)
        else:
            dt_started = started_at
        if dt_started.tzinfo is None:
            dt_started = dt_started.replace(tzinfo=UTC)

        query = """
            INSERT INTO stream_sessions (
                stream_id,
                channel_id,
                started_at,
                title,
                category_name,
                is_live,
                last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, TRUE, NOW())
            ON CONFLICT (stream_id) DO UPDATE SET
                title = COALESCE(EXCLUDED.title, stream_sessions.title),
                category_name = COALESCE(
                    EXCLUDED.category_name, stream_sessions.category_name
                ),
                last_seen_at = NOW(),
                is_live = TRUE
            RETURNING 
                stream_id,
                channel_id,
                title,
                category_name,
                is_live,
                started_at,
                ended_at,
                last_seen_at,
                peak_viewers,
                close_reason;
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                query, stream_id, channel_id, dt_started, title, category_name
            )
        return dict(row) if row else {}

    async def update_session_viewers(self, stream_id: str, viewers: int) -> bool:
        """Actualiza last_seen_at y el récord de peak_viewers de la sesión."""
        query = """
            UPDATE stream_sessions
            SET 
                last_seen_at = NOW(),
                peak_viewers = GREATEST(COALESCE(peak_viewers, 0), $2)
            WHERE stream_id = $1;
        """
        async with self._db.acquire() as conn:
            result = await conn.execute(query, stream_id, viewers)
        return result == "UPDATE 1"

    async def close_session(
        self,
        stream_id: str,
        ended_at: datetime | str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Cierra una sesión marcando ended_at, close_reason e is_live=FALSE."""
        if ended_at is None:
            dt_ended = datetime.now(UTC)
        elif isinstance(ended_at, str):
            dt_ended = datetime.fromisoformat(ended_at)
        else:
            dt_ended = ended_at
        if dt_ended.tzinfo is None:
            dt_ended = dt_ended.replace(tzinfo=UTC)

        query = """
            UPDATE stream_sessions
            SET 
                ended_at = $1,
                close_reason = $2,
                is_live = FALSE
            WHERE stream_id = $3 AND ended_at IS NULL;
        """
        async with self._db.acquire() as conn:
            result = await conn.execute(query, dt_ended, reason, stream_id)
        return result == "UPDATE 1"

    async def save_viewer_snapshot(
        self,
        channel_id: str,
        stream_id: str,
        viewer_count: int,
        recorded_at: datetime | str | None = None,
    ) -> int | None:
        """Inserta una muestra de espectadores en viewer_snapshots."""
        if recorded_at is None:
            dt_recorded = datetime.now(UTC)
        elif isinstance(recorded_at, str):
            dt_recorded = datetime.fromisoformat(recorded_at)
        else:
            dt_recorded = recorded_at
        if dt_recorded.tzinfo is None:
            dt_recorded = dt_recorded.replace(tzinfo=UTC)

        query = """
            INSERT INTO viewer_snapshots (
                channel_id, stream_id, viewer_count, recorded_at
            )
            VALUES ($1, $2, $3, $4)
            RETURNING id;
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                query, channel_id, stream_id, viewer_count, dt_recorded
            )
        return int(row["id"]) if row else None

    async def save_stream_event(
        self,
        channel_id: str,
        stream_id: str | None,
        event_type: str,
        event_data: dict[str, Any],
        timestamp: datetime | str | None = None,
    ) -> int | None:
        """Inserta un evento de Twitch con carga JSONB en stream_events."""
        if timestamp is None:
            dt_timestamp = datetime.now(UTC)
        elif isinstance(timestamp, str):
            dt_timestamp = datetime.fromisoformat(timestamp)
        else:
            dt_timestamp = timestamp
        if dt_timestamp.tzinfo is None:
            dt_timestamp = dt_timestamp.replace(tzinfo=UTC)

        raw_json = json.dumps(event_data)

        query = """
            INSERT INTO stream_events (
                channel_id, stream_id, event_type, event_data, timestamp
            )
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING id;
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                query, channel_id, stream_id, event_type, raw_json, dt_timestamp
            )
        return int(row["id"]) if row else None

    async def get_orphan_sessions(
        self, channel_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retorna sesiones abiertas sin ended_at y con is_live=TRUE."""
        query = """
            SELECT 
                stream_id,
                channel_id,
                title,
                category_name,
                is_live,
                started_at,
                ended_at,
                last_seen_at,
                peak_viewers,
                close_reason
            FROM stream_sessions
            WHERE ended_at IS NULL AND is_live = TRUE
              AND ($1::text IS NULL OR channel_id = $1)
            ORDER BY started_at DESC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id)
        return [dict(row) for row in rows]

    async def close_orphan_session_fast(self, stream_id: str) -> dict[str, Any] | None:
        """Cierra una sesión huérfana estimando el instante de cierre en <0.5ms."""
        query = """
            UPDATE stream_sessions s
            SET 
                ended_at = COALESCE(
                    snap.max_ts::timestamptz,
                    evt.max_ts::timestamptz,
                    chat.max_ts::timestamptz,
                    s.started_at::timestamptz
                ),
                close_reason = 'orphan_recovery_fast',
                is_live = FALSE
            FROM (
                SELECT stream_id, started_at
                FROM stream_sessions
                WHERE stream_id = $1 AND ended_at IS NULL AND is_live = TRUE
            ) orphaned
            LEFT JOIN LATERAL (
                SELECT recorded_at AS max_ts
                FROM viewer_snapshots
                WHERE stream_id = orphaned.stream_id
                ORDER BY recorded_at DESC
                LIMIT 1
            ) snap ON TRUE
            LEFT JOIN LATERAL (
                SELECT timestamp AS max_ts
                FROM stream_events
                WHERE stream_id = orphaned.stream_id
                ORDER BY timestamp DESC
                LIMIT 1
            ) evt ON TRUE
            LEFT JOIN LATERAL (
                SELECT timestamp AS max_ts
                FROM chat_history
                WHERE stream_id = orphaned.stream_id
                ORDER BY timestamp DESC
                LIMIT 1
            ) chat ON TRUE
            WHERE s.stream_id = orphaned.stream_id
            RETURNING 
                s.stream_id,
                s.channel_id,
                s.started_at,
                s.ended_at,
                s.close_reason,
                s.is_live;
        """
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(query, stream_id)
        return dict(row) if row else None

    async def get_chat_activity(
        self,
        channel_id: str,
        stream_id: str | None = None,
        interval_minutes: int = 5,
    ) -> list[dict[str, Any]]:
        """Agrupa mensajes por intervalos con date_bin y generate_series."""
        safe_interval = max(1, interval_minutes)

        if stream_id:
            query = """
                WITH session_meta AS (
                    SELECT 
                        stream_id,
                        channel_id,
                        started_at,
                        COALESCE(ended_at, NOW()) AS ended_at
                    FROM stream_sessions
                    WHERE stream_id = $1 AND channel_id = $2
                ),
                grid AS (
                    SELECT generate_series(
                        sm.started_at,
                        GREATEST(sm.ended_at, sm.started_at),
                        MAKE_INTERVAL(mins => $3)
                    ) AS bucket_start
                    FROM session_meta sm
                ),
                binned_msgs AS (
                    SELECT 
                        date_bin(
                            MAKE_INTERVAL(mins => $3),
                            c.timestamp::timestamptz,
                            sm.started_at
                        ) AS bucket_start,
                        COUNT(*) AS message_count,
                        COUNT(DISTINCT c.user_id) AS unique_chatters
                    FROM chat_history c
                    CROSS JOIN session_meta sm
                    WHERE c.stream_id = $1
                    GROUP BY bucket_start
                )
                SELECT 
                    g.bucket_start,
                    g.bucket_start + MAKE_INTERVAL(mins => $3) AS bucket_end,
                    FLOOR(
                        EXTRACT(EPOCH FROM (g.bucket_start - sm.started_at)) / 60
                    )::int AS stream_minute,
                    COALESCE(b.message_count, 0)::int AS message_count,
                    COALESCE(b.unique_chatters, 0)::int AS unique_chatters
                FROM grid g
                CROSS JOIN session_meta sm
                LEFT JOIN binned_msgs b ON g.bucket_start = b.bucket_start
                ORDER BY g.bucket_start ASC;
            """
            async with self._db.acquire() as conn:
                rows: list[asyncpg.Record] = await conn.fetch(
                    query, stream_id, channel_id, safe_interval
                )
        else:
            query = """
                WITH bounds AS (
                    SELECT 
                        NOW() - INTERVAL '24 hours' AS start_time,
                        NOW() AS end_time
                ),
                grid AS (
                    SELECT generate_series(
                        date_bin(
                            MAKE_INTERVAL(mins => $2),
                            b.start_time,
                            '2000-01-01 00:00:00+00'::timestamptz
                        ),
                        b.end_time,
                        MAKE_INTERVAL(mins => $2)
                    ) AS bucket_start
                    FROM bounds b
                ),
                binned_msgs AS (
                    SELECT 
                        date_bin(
                            MAKE_INTERVAL(mins => $2),
                            c.timestamp::timestamptz,
                            '2000-01-01 00:00:00+00'::timestamptz
                        ) AS bucket_start,
                        COUNT(*) AS message_count,
                        COUNT(DISTINCT c.user_id) AS unique_chatters
                    FROM chat_history c
                    WHERE c.channel_id = $1
                      AND c.timestamp::timestamptz >= (NOW() - INTERVAL '24 hours')
                    GROUP BY bucket_start
                )
                SELECT 
                    g.bucket_start,
                    g.bucket_start + MAKE_INTERVAL(mins => $2) AS bucket_end,
                    NULL::int AS stream_minute,
                    COALESCE(b.message_count, 0)::int AS message_count,
                    COALESCE(b.unique_chatters, 0)::int AS unique_chatters
                FROM grid g
                LEFT JOIN binned_msgs b ON g.bucket_start = b.bucket_start
                ORDER BY g.bucket_start ASC;
            """
            async with self._db.acquire() as conn:
                rows = await conn.fetch(query, channel_id, safe_interval)

        return [dict(row) for row in rows]

    async def get_top_chatters(
        self,
        channel_id: str,
        since: datetime | str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Devuelve los usuarios con más mensajes agrupados por CTE optimizado."""
        if since is None:
            dt_since = None
        elif isinstance(since, str):
            dt_since = datetime.fromisoformat(since)
        else:
            dt_since = since
        if dt_since is not None and dt_since.tzinfo is None:
            dt_since = dt_since.replace(tzinfo=UTC)

        query = """
            WITH top_senders AS (
                SELECT 
                    user_id,
                    COUNT(*) AS msg_count
                FROM chat_history
                WHERE channel_id = $1
                  AND (
                      $2::timestamptz IS NULL 
                      OR timestamp::timestamptz >= $2::timestamptz
                  )
                GROUP BY user_id
                ORDER BY msg_count DESC
                LIMIT $3
            )
            SELECT 
                ts.user_id,
                COALESCE(u.username, ts.user_id) AS username,
                u.display_name,
                u.nickname,
                u.profile_image_url,
                ts.msg_count::int
            FROM top_senders ts
            LEFT JOIN users u ON ts.user_id = u.user_id
            ORDER BY ts.msg_count DESC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(
                query, channel_id, dt_since, limit
            )
        return [dict(row) for row in rows]

    async def get_followers_growth(
        self,
        channel_id: str,
        period: str = "day",
        since: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        """Calcula altas, bajas, balance neto y acumulado de seguidores."""
        valid_periods = {"day", "week", "month"}
        safe_period = period if period in valid_periods else "day"

        if since is None:
            dt_since = None
        elif isinstance(since, str):
            dt_since = datetime.fromisoformat(since)
        else:
            dt_since = since
        if dt_since is not None and dt_since.tzinfo is None:
            dt_since = dt_since.replace(tzinfo=UTC)

        query = f"""
            WITH events AS (
                SELECT 
                    date_trunc(
                        '{safe_period}', followed_at::timestamptz
                    ) AS period_start,
                    1 AS gained,
                    0 AS lost
                FROM channel_users
                WHERE channel_id = $1 
                  AND followed_at IS NOT NULL
                  AND (
                      $2::timestamptz IS NULL 
                      OR followed_at::timestamptz >= $2::timestamptz
                  )
                
                UNION ALL
                
                SELECT 
                    date_trunc(
                        '{safe_period}', unfollowed_at::timestamptz
                    ) AS period_start,
                    0 AS gained,
                    1 AS lost
                FROM channel_users
                WHERE channel_id = $1 
                  AND unfollowed_at IS NOT NULL
                  AND (
                      $2::timestamptz IS NULL 
                      OR unfollowed_at::timestamptz >= $2::timestamptz
                  )
            )
            SELECT 
                period_start,
                SUM(gained)::int AS follows_gained,
                SUM(lost)::int AS follows_lost,
                (SUM(gained) - SUM(lost))::int AS net_growth,
                SUM(SUM(gained) - SUM(lost)) OVER (
                    ORDER BY period_start ASC
                )::int AS cumulative_growth
            FROM events
            GROUP BY period_start
            ORDER BY period_start ASC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, channel_id, dt_since)
        return [dict(row) for row in rows]

    async def get_viewer_timeline(self, stream_id: str) -> list[dict[str, Any]]:
        """Retorna las muestras de espectadores con el minuto de transmisión."""
        query = """
            SELECT 
                v.id,
                v.stream_id,
                v.channel_id,
                v.viewer_count,
                v.recorded_at,
                FLOOR(
                    EXTRACT(EPOCH FROM (v.recorded_at - s.started_at)) / 60
                )::int AS stream_minute
            FROM viewer_snapshots v
            JOIN stream_sessions s ON v.stream_id = s.stream_id
            WHERE v.stream_id = $1
            ORDER BY v.recorded_at ASC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, stream_id)
        return [dict(row) for row in rows]

    async def get_stream_sessions(
        self, channel_id: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Lista las sesiones de transmisión ordenadas cronológicamente."""
        query = """
            SELECT 
                stream_id,
                channel_id,
                title,
                category_name,
                is_live,
                started_at,
                ended_at,
                last_seen_at,
                peak_viewers,
                close_reason
            FROM stream_sessions
            WHERE ($1::text IS NULL OR channel_id = $1)
            ORDER BY started_at DESC
            LIMIT $2;
        """
        rows: list[asyncpg.Record] = []
        for attempt in range(2):
            try:
                async with self._db.acquire() as conn:
                    rows = await conn.fetch(query, channel_id, limit)
                break
            except (
                asyncpg.ConnectionDoesNotExistError,
                asyncpg.InterfaceError,
                OSError,
            ) as e:
                if attempt == 0:
                    LOGGER.warning(
                        "Conexión perdida en stream sessions (%s). Reintentando...",
                        e,
                    )
                    await asyncio.sleep(0.15)
                    continue
                raise
        return [dict(row) for row in rows]

    async def get_stream_event_summary(self, stream_id: str) -> list[dict[str, Any]]:
        """Agrupa métricas clave por tipo de evento en la sesión indicada."""
        query = """
            SELECT 
                event_type,
                COUNT(*)::int AS event_count,
                CASE 
                    WHEN event_type = 'raid' THEN 
                        SUM(
                            COALESCE(
                                (event_data->>'viewer_count')::numeric, 0
                            )::int
                        )
                    WHEN event_type = 'cheer' THEN 
                        SUM(
                            COALESCE((event_data->>'bits')::numeric, 0)::int
                        )
                    WHEN event_type = 'channel_points' THEN 
                        SUM(
                            COALESCE(
                                (event_data->>'reward_cost')::numeric, 0
                            )::int
                        )
                    ELSE NULL
                END AS total_metric_value
            FROM stream_events
            WHERE stream_id = $1
            GROUP BY event_type
            ORDER BY event_count DESC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, stream_id)
        return [dict(row) for row in rows]

    async def get_stream_event_timeline(self, stream_id: str) -> list[dict[str, Any]]:
        """Devuelve eventos con minuto relativo y carga JSON deserializada."""
        query = """
            SELECT 
                e.id,
                e.stream_id,
                e.channel_id,
                e.event_type,
                e.event_data,
                e.timestamp,
                FLOOR(
                    EXTRACT(EPOCH FROM (e.timestamp - s.started_at)) / 60
                )::int AS stream_minute
            FROM stream_events e
            JOIN stream_sessions s ON e.stream_id = s.stream_id
            WHERE e.stream_id = $1
            ORDER BY e.timestamp ASC;
        """
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, stream_id)

        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if isinstance(item.get("event_data"), str):
                with contextlib.suppress(Exception):
                    item["event_data"] = json.loads(item["event_data"])
            results.append(item)
        return results
