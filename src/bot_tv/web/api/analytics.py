"""Endpoints REST para el módulo de analíticas y telemetría de streams."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bot_tv.database.repositories.base import to_utc_datetime
from bot_tv.web.api.helpers import _json_err, _json_ok, _parse_int_param

if TYPE_CHECKING:
    from bot_tv.bot import Bot
    from bot_tv.database import AnalyticsRepository

LOGGER = logging.getLogger(__name__)

MSG_CHANNEL_REQUIRED = (
    "Parámetro 'channel_id' requerido o no se pudo determinar el canal predeterminado."
)
MSG_INTERNAL_ERROR = "Error interno del servidor."
MSG_SERVICE_UNAVAILABLE = "Servicio de analíticas no disponible."
MAX_INTERVAL_MINUTES = 1440
MAX_ANALYTICS_LIMIT = 100
MAX_MESSAGES_LIMIT = 200
DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_ANALYTICS_LIMIT = 10
DEFAULT_MESSAGES_LIMIT = 100
SECONDS_PER_MINUTE = 60.0

_EVENT_DETAIL_LABELS: dict[str, tuple[str, str]] = {
    "raid": ("raid", "raids"),
    "subscription": ("sub", "subs"),
    "subscription_gift": ("regalo", "regalos"),
    "subscription_message": ("resub", "resubs"),
    "channel_points": ("canje", "canjes"),
}


def _safe_utc_datetime(value: Any) -> datetime | None:
    """Convierte datetime o string ISO a datetime UTC sin propagar errores."""
    if not isinstance(value, (datetime, str)):
        return None
    try:
        return to_utc_datetime(value)
    except ValueError, TypeError:
        return None


def _format_events_detail(event_summary: list[dict[str, Any]]) -> str:
    """Construye un resumen legible en español a partir de event_summary."""
    parts: list[str] = []
    for item in event_summary:
        event_type = str(item.get("event_type") or "").strip().lower()
        count = int(item.get("event_count") or 0)
        if not event_type or count <= 0:
            continue

        if event_type == "cheer":
            bits = int(item.get("total_metric_value") or 0)
            if bits > 0:
                unit = "bit" if bits == 1 else "bits"
                parts.append(f"{bits} {unit}")
            else:
                unit = "cheer" if count == 1 else "cheers"
                parts.append(f"{count} {unit}")
            continue

        if event_type == "channel_points":
            unit = "canje" if count == 1 else "canjes"
            reward_title = str(item.get("reward_title") or "").strip()
            if reward_title:
                parts.append(f"{count} {unit} ({reward_title})")
            else:
                parts.append(f"{count} {unit}")
            continue

        labels = _EVENT_DETAIL_LABELS.get(event_type)
        if labels is not None:
            singular, plural = labels
            parts.append(f"{count} {singular if count == 1 else plural}")
        else:
            parts.append(f"{count} {event_type}")

    return " · ".join(parts)


def _get_bot(request: Request) -> Bot:
    """Obtiene la instancia de Bot desde el estado de la aplicación Starlette."""
    bot: Bot | None = getattr(request.app.state, "bot", None)
    if bot is None:
        raise RuntimeError("Instancia de Bot no disponible en request.app.state.bot")
    return bot


def _get_analytics_repo(bot: Bot) -> AnalyticsRepository:
    """Obtiene el repositorio de analíticas desde la instancia del bot."""
    repo = getattr(bot, "analytics_repo", None)
    if repo is None:
        raise RuntimeError("AnalyticsRepository no inicializado en bot.analytics_repo")
    return repo


async def _resolve_channel_id(bot: Bot, channel_id: str | None) -> str | None:
    """Resuelve el channel_id explícito o busca el ID del primer canal disponible."""
    if channel_id and channel_id.strip():
        return channel_id.strip()
    if hasattr(bot, "get_channels"):
        try:
            channels = await bot.get_channels()
            if channels and "user_id" in channels[0]:
                return channels[0]["user_id"]
        except Exception as e:
            LOGGER.warning("Error al resolver canales predeterminados: %s", e)
    return None


async def endpoint_analytics_chat_activity(request: Request) -> Response:
    """Obtiene la actividad del chat agrupada por intervalos temporales."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        raw_stream_id = request.query_params.get("stream_id")
        stream_id = (
            raw_stream_id.strip() if raw_stream_id and raw_stream_id.strip() else None
        )

        interval_minutes = _parse_int_param(
            request,
            "interval_minutes",
            DEFAULT_INTERVAL_MINUTES,
            min_val=1,
            max_val=MAX_INTERVAL_MINUTES,
            strict_min=True,
        )
        if isinstance(interval_minutes, JSONResponse):
            return interval_minutes

        activity = await repo.get_chat_activity(
            channel_id=channel_id,
            stream_id=stream_id,
            interval_minutes=interval_minutes,
        )
        return _json_ok(activity)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar actividad del chat: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_top_chatters(request: Request) -> Response:
    """Obtiene los usuarios más activos del chat por sesión o período."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        raw_stream_id = request.query_params.get("stream_id")
        stream_id = (
            raw_stream_id.strip() if raw_stream_id and raw_stream_id.strip() else None
        )

        limit = _parse_int_param(
            request,
            "limit",
            DEFAULT_ANALYTICS_LIMIT,
            min_val=1,
            max_val=MAX_ANALYTICS_LIMIT,
            strict_min=True,
        )
        if isinstance(limit, JSONResponse):
            return limit

        since: datetime | None = None
        if stream_id is None:
            period = request.query_params.get("period", "24h").strip().lower()
            valid_periods = {"24h", "7d", "30d", "all"}
            if period not in valid_periods:
                return _json_err(
                    "El parámetro 'period' debe ser uno de: '24h', '7d', '30d', 'all'."
                )

            now = datetime.now(UTC)
            if period == "24h":
                since = now - timedelta(hours=24)
            elif period == "7d":
                since = now - timedelta(days=7)
            elif period == "30d":
                since = now - timedelta(days=30)

        top_chatters = await repo.get_top_chatters(
            channel_id=channel_id,
            since=since,
            limit=limit,
            stream_id=stream_id,
        )
        return _json_ok(top_chatters)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar top chatters: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_followers_growth(request: Request) -> Response:
    """Obtiene el crecimiento de seguidores agrupado por día, semana o mes."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        period = request.query_params.get("period", "day").strip().lower()
        if period not in {"day", "week", "month"}:
            return _json_err(
                "El parámetro 'period' debe ser uno de: 'day', 'week', 'month'."
            )

        raw_since = request.query_params.get("since")
        since: datetime | None = None
        if raw_since and raw_since.strip():
            try:
                since = datetime.fromisoformat(raw_since.strip())
            except ValueError, TypeError:
                return _json_err(
                    "El parámetro 'since' debe ser una fecha ISO 8601 válida."
                )

        growth = await repo.get_followers_growth(
            channel_id=channel_id,
            period=period,
            since=since,
        )
        return _json_ok(growth)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar crecimiento de seguidores: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_followers_events(request: Request) -> Response:
    """Obtiene los eventos de alta y baja de seguidores de una sesión."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_stream_id = request.query_params.get("stream_id")
        if not raw_stream_id or not raw_stream_id.strip():
            return _json_err("Parámetro 'stream_id' requerido.")
        stream_id = raw_stream_id.strip()

        channel_id = await _resolve_channel_id(
            bot, request.query_params.get("channel_id")
        )
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        data = await repo.get_session_follower_events(
            channel_id=channel_id,
            stream_id=stream_id,
        )
        return _json_ok(data)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar eventos de seguidores de la sesión: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_messages(request: Request) -> Response:
    """Obtiene mensajes de chat de una sesión con filtros y paginación."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_stream_id = request.query_params.get("stream_id")
        if not raw_stream_id or not raw_stream_id.strip():
            return _json_err("Parámetro 'stream_id' requerido.")
        stream_id = raw_stream_id.strip()

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        raw_since = (request.query_params.get("since") or "").strip()
        since_dt: datetime | None = None
        if raw_since:
            try:
                since_dt = to_utc_datetime(raw_since)
            except ValueError, TypeError:
                return _json_err("Parámetro de fecha inválido.", status_code=400)

        raw_until = (request.query_params.get("until") or "").strip()
        until_dt: datetime | None = None
        if raw_until:
            try:
                until_dt = to_utc_datetime(raw_until)
            except ValueError, TypeError:
                return _json_err("Parámetro de fecha inválido.", status_code=400)

        user_id = (request.query_params.get("user_id") or "").strip() or None

        limit = _parse_int_param(
            request,
            "limit",
            DEFAULT_MESSAGES_LIMIT,
            min_val=1,
            max_val=MAX_MESSAGES_LIMIT,
            strict_min=True,
        )
        if isinstance(limit, JSONResponse):
            return limit

        offset = _parse_int_param(
            request,
            "offset",
            0,
            min_val=0,
            max_val=None,
            strict_min=False,
        )
        if isinstance(offset, JSONResponse):
            return offset

        result = await repo.get_session_messages(
            channel_id=channel_id,
            stream_id=stream_id,
            since=since_dt,
            until=until_dt,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        return _json_ok(result)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar mensajes de la sesión: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_viewers_timeline(request: Request) -> Response:
    """Obtiene la curva temporal de espectadores para una transmisión."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_stream_id = request.query_params.get("stream_id")
        if not raw_stream_id or not raw_stream_id.strip():
            return _json_err("Parámetro 'stream_id' requerido.")
        stream_id = raw_stream_id.strip()

        timeline = await repo.get_viewer_timeline(stream_id=stream_id)
        return _json_ok(timeline)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar línea de tiempo de espectadores: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_stream_events(request: Request) -> Response:
    """Obtiene el resumen y la línea de tiempo de eventos de una transmisión."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_stream_id = request.query_params.get("stream_id")
        if not raw_stream_id or not raw_stream_id.strip():
            return _json_err("Parámetro 'stream_id' requerido.")
        stream_id = raw_stream_id.strip()

        summary, timeline = await asyncio.gather(
            repo.get_stream_event_summary(stream_id),
            repo.get_stream_event_timeline(stream_id),
        )
        return _json_ok({"summary": summary, "timeline": timeline})
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar eventos de la transmisión: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_stream_sessions(request: Request) -> Response:
    """Obtiene el listado cronológico de sesiones de transmisión del canal."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)

        limit = _parse_int_param(
            request,
            "limit",
            DEFAULT_ANALYTICS_LIMIT,
            min_val=1,
            max_val=MAX_ANALYTICS_LIMIT,
            strict_min=True,
        )
        if isinstance(limit, JSONResponse):
            return limit

        sessions = await repo.get_stream_sessions(channel_id=channel_id, limit=limit)
        return _json_ok(sessions)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consultar sesiones de transmisión: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)


async def endpoint_analytics_overview(request: Request) -> Response:
    """Consolida métricas clave para la sesión actual o más reciente."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)

        raw_stream_id = request.query_params.get("stream_id")
        target_stream_id = (
            raw_stream_id.strip() if raw_stream_id and raw_stream_id.strip() else None
        )

        session: dict[str, Any] | None = None
        if target_stream_id:
            session = await repo.get_stream_session_by_id(
                target_stream_id, channel_id=channel_id
            )
        else:
            recent_sessions = await repo.get_stream_sessions(
                channel_id=channel_id, limit=1
            )
            if recent_sessions:
                session = recent_sessions[0]
                target_stream_id = str(session.get("stream_id"))

        if not session and not target_stream_id:
            return _json_ok(
                {
                    "stream_id": None,
                    "title": None,
                    "category_name": None,
                    "started_at": None,
                    "ended_at": None,
                    "duration_seconds": 0,
                    "is_live": False,
                    "peak_viewers": 0,
                    "avg_viewers": None,
                    "total_messages": 0,
                    "messages_per_minute": 0.0,
                    "total_events": 0,
                    "event_summary": [],
                    "events_detail": "",
                    "new_followers": 0,
                    "lost_followers": 0,
                    "net_followers": 0,
                }
            )

        if not channel_id and session and session.get("channel_id"):
            channel_id = str(session["channel_id"])

        is_live = bool(session.get("is_live", False)) if session else False
        started_at = _safe_utc_datetime(session.get("started_at")) if session else None
        ended_at = _safe_utc_datetime(session.get("ended_at")) if session else None
        duration_seconds = (
            max(0, int(((ended_at or datetime.now(UTC)) - started_at).total_seconds()))
            if started_at is not None
            else 0
        )

        event_summary: list[dict[str, Any]] = []
        total_events = 0
        total_messages = 0
        viewer_stats: dict[str, int | None] = {
            "avg_viewers": None,
            "peak_viewers": None,
            "sample_count": 0,
        }
        followers_balance: dict[str, int] = {
            "new_followers": 0,
            "lost_followers": 0,
            "net_followers": 0,
        }

        if target_stream_id:
            if session and channel_id and started_at is not None:
                (
                    event_summary,
                    total_messages,
                    viewer_stats,
                    followers_balance,
                ) = await asyncio.gather(
                    repo.get_stream_event_summary(target_stream_id),
                    repo.get_stream_message_count(target_stream_id),
                    repo.get_viewer_stats(target_stream_id),
                    repo.get_followers_balance(channel_id, started_at, end_at=ended_at),
                )
            else:
                (
                    event_summary,
                    total_messages,
                    viewer_stats,
                ) = await asyncio.gather(
                    repo.get_stream_event_summary(target_stream_id),
                    repo.get_stream_message_count(target_stream_id),
                    repo.get_viewer_stats(target_stream_id),
                )
            total_events = sum(
                int(item.get("event_count") or 0) for item in event_summary
            )

        peak_viewers = max(
            int(session.get("peak_viewers") or 0) if session else 0,
            viewer_stats.get("peak_viewers") or 0,
        )
        avg_viewers = viewer_stats.get("avg_viewers")
        messages_per_minute = (
            round(total_messages / (duration_seconds / SECONDS_PER_MINUTE), 1)
            if duration_seconds > 0
            else 0.0
        )

        overview_data = {
            "stream_id": target_stream_id,
            "title": session.get("title") if session else None,
            "category_name": session.get("category_name") if session else None,
            "started_at": session.get("started_at") if session else None,
            "ended_at": session.get("ended_at") if session else None,
            "duration_seconds": duration_seconds,
            "is_live": is_live,
            "peak_viewers": peak_viewers,
            "avg_viewers": avg_viewers,
            "total_messages": total_messages,
            "messages_per_minute": messages_per_minute,
            "total_events": total_events,
            "event_summary": event_summary,
            "events_detail": _format_events_detail(event_summary),
            "new_followers": followers_balance.get("new_followers", 0),
            "lost_followers": followers_balance.get("lost_followers", 0),
            "net_followers": followers_balance.get("net_followers", 0),
        }
        return _json_ok(overview_data)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consolidar resumen de analíticas: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)
