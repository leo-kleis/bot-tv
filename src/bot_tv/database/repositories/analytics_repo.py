from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import BaseRepository, to_utc_datetime

if TYPE_CHECKING:
    import asyncpg

LOGGER = logging.getLogger(__name__)

_MAX_SESSION_MESSAGES_LIMIT = 200


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
        dt_started = to_utc_datetime(started_at) or datetime.now(UTC)

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
        row = await self._fetchrow(
            query,
            stream_id,
            channel_id,
            dt_started,
            title,
            category_name,
            context_label="create_or_get_session",
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
        result = await self._execute(
            query, stream_id, viewers, context_label="update_session_viewers"
        )
        return result == "UPDATE 1"

    async def close_session(
        self,
        stream_id: str,
        ended_at: datetime | str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Cierra una sesión marcando ended_at, close_reason e is_live=FALSE."""
        dt_ended = to_utc_datetime(ended_at) or datetime.now(UTC)

        query = """
            UPDATE stream_sessions
            SET 
                ended_at = $1,
                close_reason = $2,
                is_live = FALSE
            WHERE stream_id = $3 AND ended_at IS NULL;
        """
        result = await self._execute(
            query, dt_ended, reason, stream_id, context_label="close_session"
        )
        return result == "UPDATE 1"

    async def save_viewer_snapshot(
        self,
        channel_id: str,
        stream_id: str,
        viewer_count: int,
        recorded_at: datetime | str | None = None,
    ) -> int | None:
        """Inserta una muestra de espectadores en viewer_snapshots."""
        dt_recorded = to_utc_datetime(recorded_at) or datetime.now(UTC)

        query = """
            INSERT INTO viewer_snapshots (
                channel_id, stream_id, viewer_count, recorded_at
            )
            VALUES ($1, $2, $3, $4)
            RETURNING id;
        """
        row = await self._fetchrow(
            query,
            channel_id,
            stream_id,
            viewer_count,
            dt_recorded,
            context_label="save_viewer_snapshot",
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
        dt_timestamp = to_utc_datetime(timestamp) or datetime.now(UTC)
        raw_json = json.dumps(event_data)

        query = """
            INSERT INTO stream_events (
                channel_id, stream_id, event_type, event_data, timestamp
            )
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING id;
        """
        row = await self._fetchrow(
            query,
            channel_id,
            stream_id,
            event_type,
            raw_json,
            dt_timestamp,
            context_label="save_stream_event",
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
        rows = await self._fetch(query, channel_id, context_label="get_orphan_sessions")
        return [dict(row) for row in rows]

    async def close_orphan_session_fast(self, stream_id: str) -> dict[str, Any] | None:
        """Cierra una sesión huérfana estimando el instante de cierre en <0.5ms."""
        query = """
            UPDATE stream_sessions s
            SET 
                ended_at = COALESCE(
                    snap.max_ts,
                    evt.max_ts,
                    chat.max_ts,
                    s.started_at
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
        row = await self._fetchrow(
            query, stream_id, context_label="close_orphan_session_fast"
        )
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
                            c.timestamp,
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
            rows = await self._fetch(
                query,
                stream_id,
                channel_id,
                safe_interval,
                context_label="get_chat_activity",
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
                            c.timestamp,
                            '2000-01-01 00:00:00+00'::timestamptz
                        ) AS bucket_start,
                        COUNT(*) AS message_count,
                        COUNT(DISTINCT c.user_id) AS unique_chatters
                    FROM chat_history c
                    WHERE c.channel_id = $1
                      AND c.timestamp >= (NOW() - INTERVAL '24 hours')
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
            rows = await self._fetch(
                query,
                channel_id,
                safe_interval,
                context_label="get_chat_activity",
            )

        return [dict(row) for row in rows]

    async def get_top_chatters(
        self,
        channel_id: str,
        since: datetime | str | None = None,
        limit: int = 10,
        stream_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Devuelve los usuarios con más mensajes agrupados por CTE optimizado."""
        clean_stream_id = stream_id.strip() if stream_id and stream_id.strip() else None
        if clean_stream_id is not None:
            where_filter = "AND stream_id = $2"
            filter_arg: datetime | str | None = clean_stream_id
        else:
            where_filter = (
                "AND ($2::timestamptz IS NULL OR timestamp >= $2::timestamptz)"
            )
            filter_arg = to_utc_datetime(since)

        query = f"""
            WITH top_senders AS (
                SELECT 
                    user_id,
                    COUNT(*) AS msg_count
                FROM chat_history
                WHERE channel_id = $1
                  {where_filter}
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
        """  # noqa: S608
        rows = await self._fetch(
            query, channel_id, filter_arg, limit, context_label="get_top_chatters"
        )
        return [dict(row) for row in rows]

    async def get_viewer_stats(self, stream_id: str) -> dict[str, int | None]:
        """Calcula promedio, pico y muestras de espectadores para una sesión."""
        query = """
            SELECT
                ROUND(AVG(viewer_count))::int AS avg_viewers,
                MAX(viewer_count)::int AS peak_viewers,
                COUNT(*)::int AS sample_count
            FROM viewer_snapshots
            WHERE stream_id = $1;
        """
        row = await self._fetchrow(query, stream_id, context_label="get_viewer_stats")
        sample_count = int(row["sample_count"] or 0) if row else 0
        if not row or sample_count == 0:
            return {
                "avg_viewers": None,
                "peak_viewers": None,
                "sample_count": 0,
            }
        return {
            "avg_viewers": (
                int(row["avg_viewers"]) if row["avg_viewers"] is not None else None
            ),
            "peak_viewers": (
                int(row["peak_viewers"]) if row["peak_viewers"] is not None else None
            ),
            "sample_count": sample_count,
        }

    async def get_followers_balance(
        self,
        channel_id: str,
        start_at: datetime | str,
        end_at: datetime | str | None = None,
    ) -> dict[str, int]:
        """Calcula altas, bajas y balance neto de seguidores en un rango temporal."""
        dt_start = to_utc_datetime(start_at)
        if dt_start is None:
            return {"new_followers": 0, "lost_followers": 0, "net_followers": 0}
        dt_end = to_utc_datetime(end_at)

        query = """
            SELECT
                (
                    SELECT COUNT(*)::int
                    FROM channel_users
                    WHERE channel_id = $1
                      AND followed_at IS NOT NULL
                      AND followed_at >= $2::timestamptz
                      AND followed_at <= COALESCE($3::timestamptz, NOW())
                ) AS new_followers,
                (
                    SELECT COUNT(*)::int
                    FROM channel_users
                    WHERE channel_id = $1
                      AND unfollowed_at IS NOT NULL
                      AND unfollowed_at >= $2::timestamptz
                      AND unfollowed_at <= COALESCE($3::timestamptz, NOW())
                ) AS lost_followers;
        """
        row = await self._fetchrow(
            query,
            channel_id,
            dt_start,
            dt_end,
            context_label="get_followers_balance",
        )
        new_followers = int(row["new_followers"] or 0) if row else 0
        lost_followers = int(row["lost_followers"] or 0) if row else 0
        return {
            "new_followers": new_followers,
            "lost_followers": lost_followers,
            "net_followers": new_followers - lost_followers,
        }

    async def get_followers_growth(
        self,
        channel_id: str,
        period: str = "day",
        since: datetime | str | None = None,
    ) -> list[dict[str, Any]]:
        """Calcula altas, bajas, balance neto y acumulado de seguidores."""
        valid_periods = {"day", "week", "month"}
        safe_period = period if period in valid_periods else "day"
        dt_since = to_utc_datetime(since)

        query = """
            WITH events AS (
                SELECT 
                    date_trunc($3::text, followed_at) AS period_start,
                    1 AS gained,
                    0 AS lost
                FROM channel_users
                WHERE channel_id = $1 
                  AND followed_at IS NOT NULL
                  AND (
                      $2::timestamptz IS NULL 
                      OR followed_at >= $2::timestamptz
                  )
                
                UNION ALL
                
                SELECT 
                    date_trunc($3::text, unfollowed_at) AS period_start,
                    0 AS gained,
                    1 AS lost
                FROM channel_users
                WHERE channel_id = $1 
                  AND unfollowed_at IS NOT NULL
                  AND (
                      $2::timestamptz IS NULL 
                      OR unfollowed_at >= $2::timestamptz
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
        rows = await self._fetch(
            query,
            channel_id,
            dt_since,
            safe_period,
            context_label="get_followers_growth",
        )
        return [dict(row) for row in rows]

    async def get_viewer_timeline(
        self, stream_id: str, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Retorna las muestras de espectadores con el minuto de transmisión."""
        safe_limit = max(1, min(limit, 10000))
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
            ORDER BY v.recorded_at ASC
            LIMIT $2;
        """
        rows = await self._fetch(
            query, stream_id, safe_limit, context_label="get_viewer_timeline"
        )
        return [dict(row) for row in rows]

    async def get_stream_session_by_id(
        self, stream_id: str, channel_id: str | None = None
    ) -> dict[str, Any] | None:
        """Obtiene una sesión de transmisión individual por su stream_id."""
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
            WHERE stream_id = $1
              AND ($2::text IS NULL OR channel_id = $2);
        """
        row = await self._fetchrow(
            query, stream_id, channel_id, context_label="stream session"
        )
        return dict(row) if row else None

    async def get_stream_message_count(self, stream_id: str) -> int:
        """Devuelve el conteo total de mensajes registrados en un stream."""
        query = """
            SELECT COUNT(*)::int AS total
            FROM chat_history
            WHERE stream_id = $1;
        """
        row = await self._fetchrow(
            query, stream_id, context_label="get_stream_message_count"
        )
        return int(row["total"]) if row else 0

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
        rows = await self._fetch(
            query, channel_id, limit, context_label="stream sessions"
        )
        return [dict(row) for row in rows]

    async def get_stream_event_summary(self, stream_id: str) -> list[dict[str, Any]]:
        """Agrupa métricas clave por tipo de evento (y recompensa) en la sesión."""
        query = """
            WITH classified AS (
                SELECT
                    event_type,
                    event_data,
                    CASE
                        WHEN event_type = 'channel_points' THEN
                            COALESCE(
                                NULLIF(TRIM(event_data->>'reward_title'), ''),
                                'Recompensa'
                            )
                        ELSE NULL
                    END AS reward_title
                FROM stream_events
                WHERE stream_id = $1
            )
            SELECT
                event_type,
                reward_title,
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
            FROM classified
            GROUP BY event_type, reward_title
            ORDER BY event_count DESC, reward_title ASC NULLS LAST;
        """
        rows = await self._fetch(
            query, stream_id, context_label="get_stream_event_summary"
        )
        return [dict(row) for row in rows]

    async def get_session_messages(
        self,
        channel_id: str,
        stream_id: str,
        since: datetime | str | None = None,
        until: datetime | str | None = None,
        user_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Devuelve mensajes paginados de una sesión con filtros y total exacto."""
        safe_limit = max(1, min(limit, _MAX_SESSION_MESSAGES_LIMIT))
        safe_offset = max(0, offset)
        dt_since = to_utc_datetime(since)
        dt_until = to_utc_datetime(until)
        clean_user_id = user_id.strip() if user_id and user_id.strip() else None

        where_clauses = ["c.channel_id = $1", "c.stream_id = $2"]
        params: list[Any] = [channel_id, stream_id]

        def _p() -> str:
            return f"${len(params) + 1}"

        if dt_since is not None:
            where_clauses.append(f"c.timestamp >= {_p()}::timestamptz")
            params.append(dt_since)

        if dt_until is not None:
            where_clauses.append(f"c.timestamp < {_p()}::timestamptz")
            params.append(dt_until)

        if clean_user_id is not None:
            where_clauses.append(f"c.user_id = {_p()}")
            params.append(clean_user_id)

        where_sql = " AND ".join(where_clauses)
        count_query = f"""
            SELECT COUNT(*)::int AS total
            FROM chat_history c
            WHERE {where_sql};
        """  # noqa: S608
        data_query = f"""
            SELECT
                c.id,
                c.user_id,
                COALESCE(u.username, c.user_id) AS username,
                u.display_name,
                u.nickname,
                u.profile_image_url,
                c.message,
                c.timestamp
            FROM chat_history c
            LEFT JOIN users u ON c.user_id = u.user_id
            WHERE {where_sql}
            ORDER BY c.timestamp ASC, c.id ASC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2};
        """  # noqa: S608

        async def _fetch_messages(
            conn: asyncpg.Connection,
        ) -> tuple[int, list[asyncpg.Record]]:
            count_row = await conn.fetchrow(count_query, *params)
            total_count = int(count_row["total"] or 0) if count_row else 0
            page_rows = await conn.fetch(
                data_query, *params, safe_limit + 1, safe_offset
            )
            return total_count, page_rows

        total, raw_rows = await self._with_retry(
            _fetch_messages, context_label="get_session_messages"
        )
        has_more = len(raw_rows) > safe_limit
        messages = [
            {
                "id": str(row["id"]),
                "user_id": row["user_id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "nickname": row["nickname"],
                "profile_image_url": row["profile_image_url"],
                "message": row["message"],
                "timestamp": row["timestamp"],
            }
            for row in raw_rows[:safe_limit]
        ]
        return {
            "messages": messages,
            "total": total,
            "has_more": has_more,
        }

    async def get_session_follower_events(
        self, channel_id: str, stream_id: str
    ) -> dict[str, Any]:
        """Obtiene los eventos individuales de follow/unfollow durante una sesión."""
        session_query = """
            SELECT
                started_at,
                COALESCE(ended_at, NOW()) AS end_bound
            FROM stream_sessions
            WHERE stream_id = $1 AND channel_id = $2;
        """
        events_query = """
            SELECT
                evt.user_id,
                COALESCE(u.username, evt.user_id) AS username,
                u.display_name,
                u.nickname,
                u.profile_image_url,
                evt.event_kind,
                evt.event_ts
            FROM (
                SELECT
                    cu.user_id,
                    'follow' AS event_kind,
                    cu.followed_at AS event_ts
                FROM channel_users cu
                WHERE cu.channel_id = $1
                  AND cu.followed_at IS NOT NULL
                  AND cu.followed_at >= $2::timestamptz
                  AND cu.followed_at <= $3::timestamptz

                UNION ALL

                SELECT
                    cu.user_id,
                    'unfollow' AS event_kind,
                    cu.unfollowed_at AS event_ts
                FROM channel_users cu
                WHERE cu.channel_id = $1
                  AND cu.unfollowed_at IS NOT NULL
                  AND cu.unfollowed_at >= $2::timestamptz
                  AND cu.unfollowed_at <= $3::timestamptz
            ) evt
            LEFT JOIN users u ON evt.user_id = u.user_id
            ORDER BY
                evt.event_ts DESC,
                evt.event_kind ASC,
                COALESCE(u.username, evt.user_id) ASC;
        """

        async def _fetch_events(
            conn: asyncpg.Connection,
        ) -> list[asyncpg.Record] | None:
            session_row = await conn.fetchrow(session_query, stream_id, channel_id)
            if not session_row:
                return None
            dt_start = to_utc_datetime(session_row["started_at"])
            if dt_start is None:
                return None
            dt_end = to_utc_datetime(session_row["end_bound"]) or dt_start
            if dt_end < dt_start:
                dt_end = dt_start
            return await conn.fetch(events_query, channel_id, dt_start, dt_end)

        rows = await self._with_retry(
            _fetch_events, context_label="get_session_follower_events"
        )
        if rows is None:
            return {"events": [], "new_count": 0, "lost_count": 0}

        events: list[dict[str, Any]] = []
        new_count = 0
        lost_count = 0
        for row in rows:
            event_kind = str(row["event_kind"])
            if event_kind == "follow":
                new_count += 1
            else:
                lost_count += 1
            events.append(
                {
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "nickname": row["nickname"],
                    "profile_image_url": row["profile_image_url"],
                    "event_kind": event_kind,
                    "timestamp": row["event_ts"],
                }
            )
        return {
            "events": events,
            "new_count": new_count,
            "lost_count": lost_count,
        }

    async def get_stream_event_timeline(
        self, stream_id: str, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Devuelve eventos con minuto relativo y carga JSON deserializada."""
        safe_limit = max(1, min(limit, 10000))
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
            ORDER BY e.timestamp ASC
            LIMIT $2;
        """
        rows = await self._fetch(
            query, stream_id, safe_limit, context_label="get_stream_event_timeline"
        )

        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if isinstance(item.get("event_data"), str):
                with contextlib.suppress(Exception):
                    item["event_data"] = json.loads(item["event_data"])
            results.append(item)
        return results
