"""Endpoints REST para el módulo de analíticas y telemetría de streams."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

MSG_CHANNEL_REQUIRED = (
    "Parámetro 'channel_id' requerido o no se pudo determinar el canal predeterminado."
)
MSG_INTERNAL_ERROR = "Error interno del servidor."
MSG_SERVICE_UNAVAILABLE = "Servicio de analíticas no disponible."
MAX_INTERVAL_MINUTES = 1440
MAX_ANALYTICS_LIMIT = 100


def _serialize(obj: Any) -> Any:
    """Serializa recursivamente estructuras para JSON seguro."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _json_ok(data: Any = None) -> JSONResponse:
    """Genera respuesta JSON estandarizada con código 200 y serialización segura."""
    return JSONResponse({"ok": True, "data": _serialize(data)})


def _json_err(message: str, status_code: int = 400) -> JSONResponse:
    """Genera respuesta JSON estandarizada de error."""
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)


def _get_bot(request: Request) -> Bot:
    """Obtiene la instancia de Bot desde el estado de la aplicación Starlette."""
    bot: Bot | None = getattr(request.app.state, "bot", None)
    if bot is None:
        raise RuntimeError("Instancia de Bot no disponible en request.app.state.bot")
    return bot


def _get_analytics_repo(bot: Bot) -> Any:
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

        raw_interval = request.query_params.get("interval_minutes", "5")
        try:
            interval_minutes = int(raw_interval)
            if interval_minutes <= 0:
                raise ValueError
        except ValueError, TypeError:
            return _json_err(
                "El parámetro 'interval_minutes' debe ser un número entero positivo."
            )
        interval_minutes = min(interval_minutes, MAX_INTERVAL_MINUTES)

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
    """Obtiene los usuarios más activos del chat en el período especificado."""
    try:
        bot = _get_bot(request)
        repo = _get_analytics_repo(bot)

        raw_channel_id = request.query_params.get("channel_id")
        channel_id = await _resolve_channel_id(bot, raw_channel_id)
        if not channel_id:
            return _json_err(MSG_CHANNEL_REQUIRED)

        period = request.query_params.get("period", "24h").strip().lower()
        valid_periods = {"24h", "7d", "30d", "all"}
        if period not in valid_periods:
            return _json_err(
                "El parámetro 'period' debe ser uno de: '24h', '7d', '30d', 'all'."
            )

        raw_limit = request.query_params.get("limit", "10")
        try:
            limit = int(raw_limit)
            if limit <= 0:
                raise ValueError
        except ValueError, TypeError:
            return _json_err("El parámetro 'limit' debe ser un número entero positivo.")
        limit = min(limit, MAX_ANALYTICS_LIMIT)

        now = datetime.now(UTC)
        since: datetime | None
        if period == "24h":
            since = now - timedelta(hours=24)
        elif period == "7d":
            since = now - timedelta(days=7)
        elif period == "30d":
            since = now - timedelta(days=30)
        else:
            since = None

        top_chatters = await repo.get_top_chatters(
            channel_id=channel_id,
            since=since,
            limit=limit,
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

        summary = await repo.get_stream_event_summary(stream_id)
        timeline = await repo.get_stream_event_timeline(stream_id)
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

        raw_limit = request.query_params.get("limit", "10")
        try:
            limit = int(raw_limit)
            if limit <= 0:
                raise ValueError
        except ValueError, TypeError:
            return _json_err("El parámetro 'limit' debe ser un número entero positivo.")
        limit = min(limit, MAX_ANALYTICS_LIMIT)

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
                    "is_live": False,
                    "peak_viewers": 0,
                    "total_messages": 0,
                    "total_events": 0,
                    "title": None,
                    "category_name": None,
                    "started_at": None,
                    "ended_at": None,
                    "event_summary": [],
                }
            )

        if not channel_id and session and session.get("channel_id"):
            channel_id = str(session["channel_id"])

        is_live = bool(session.get("is_live", False)) if session else False
        peak_viewers = int(session.get("peak_viewers") or 0) if session else 0

        event_summary: list[dict[str, Any]] = []
        total_events = 0
        if target_stream_id:
            event_summary = await repo.get_stream_event_summary(target_stream_id)
            total_events = sum(
                int(item.get("event_count") or 0) for item in event_summary
            )

        total_messages = 0
        if target_stream_id:
            total_messages = await repo.get_stream_message_count(target_stream_id)

        overview_data = {
            "stream_id": target_stream_id,
            "title": session.get("title") if session else None,
            "category_name": session.get("category_name") if session else None,
            "started_at": session.get("started_at") if session else None,
            "ended_at": session.get("ended_at") if session else None,
            "is_live": is_live,
            "peak_viewers": peak_viewers,
            "total_messages": total_messages,
            "total_events": total_events,
            "event_summary": event_summary,
        }
        return _json_ok(overview_data)
    except RuntimeError as e:
        LOGGER.error("Error al obtener dependencias: %s", e)
        return _json_err(MSG_SERVICE_UNAVAILABLE, status_code=503)
    except Exception as e:
        LOGGER.exception("Error al consolidar resumen de analíticas: %s", e)
        return _json_err(MSG_INTERNAL_ERROR, status_code=500)
