"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import Scope
from starlette.websockets import WebSocket

from bot_tv.web.api import (
    endpoint_analytics_chat_activity,
    endpoint_analytics_followers_growth,
    endpoint_analytics_overview,
    endpoint_analytics_stream_events,
    endpoint_analytics_stream_sessions,
    endpoint_analytics_top_chatters,
    endpoint_analytics_viewers_timeline,
    endpoint_clear_agent_chat,
    endpoint_create_clip,
    endpoint_exit,
    endpoint_get_avatar,
    endpoint_get_chat_accounts,
    endpoint_get_ffz_emotes,
    endpoint_get_models,
    endpoint_get_rpm,
    endpoint_get_user_detail,
    endpoint_list_users,
    endpoint_moderation_ban,
    endpoint_moderation_delete_message,
    endpoint_moderation_purge,
    endpoint_moderation_unban,
    endpoint_search_categories,
    endpoint_search_users,
    endpoint_send_chat_message,
    endpoint_set_context_limit,
    endpoint_set_nickname,
    endpoint_switch_model,
    endpoint_sync_followers,
    endpoint_sync_user_roles,
    endpoint_talk,
    endpoint_update_stream_info,
    endpoint_update_user_roles,
    endpoint_user_messages,
)
from bot_tv.web.ws_handler import WebSocketManager

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot
    from bot_tv.event_bus import EventBus

LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

WEB_PORT = 8080
MUTATING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})
CROSS_ORIGIN_BLOCKED_MSG = "Solicitud cross-origin bloqueada."


def _apply_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Valida Same-Origin en peticiones mutadoras y añade cabeceras de seguridad."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in MUTATING_METHODS:
            sec_fetch_site = request.headers.get("sec-fetch-site", "").lower()
            if sec_fetch_site and sec_fetch_site not in ALLOWED_FETCH_SITES:
                blocked_resp = JSONResponse(
                    {"ok": False, "error": CROSS_ORIGIN_BLOCKED_MSG},
                    status_code=403,
                )
                _apply_security_headers(blocked_resp)
                return blocked_resp

            origin = request.headers.get("origin")
            if origin:
                origin_host = urlparse(origin).netloc
                host = request.headers.get("host", "")
                if origin_host != host:
                    blocked_resp = JSONResponse(
                        {"ok": False, "error": CROSS_ORIGIN_BLOCKED_MSG},
                        status_code=403,
                    )
                    _apply_security_headers(blocked_resp)
                    return blocked_resp

        response = await call_next(request)
        _apply_security_headers(response)
        return response


class NoCacheStaticFiles(StaticFiles):
    """Evita el almacenamiento en caché del navegador para archivos estáticos."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def create_app(bot: Bot, agent: TalkAgent, event_bus: EventBus) -> Starlette:
    """Crea y configura la aplicación Starlette con todos los endpoints."""
    ws_manager = WebSocketManager(event_bus, bot)
    ws_manager.register()

    async def homepage(request: Request) -> Response:
        return FileResponse(STATIC_DIR / "index.html")

    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws_manager.handle(ws)

    routes = [
        Route("/", homepage),
        Route("/sw.js", lambda r: FileResponse(STATIC_DIR / "sw.js")),
        Route("/manifest.json", lambda r: FileResponse(STATIC_DIR / "manifest.json")),
        Route(
            "/favicon.ico",
            lambda r: FileResponse(STATIC_DIR / "icons" / "icon-192.png"),
        ),
        WebSocketRoute("/ws", websocket_endpoint),
        # REST API
        Route("/api/sync_followers", endpoint_sync_followers, methods=["POST"]),
        Route("/api/set_nickname", endpoint_set_nickname, methods=["POST"]),
        Route("/api/update_user_roles", endpoint_update_user_roles, methods=["POST"]),
        Route("/api/sync_user_roles", endpoint_sync_user_roles, methods=["POST"]),
        Route("/api/switch_model", endpoint_switch_model, methods=["POST"]),
        Route("/api/agent/clear", endpoint_clear_agent_chat, methods=["POST"]),
        Route("/api/agent/context_limit", endpoint_set_context_limit, methods=["POST"]),
        Route("/api/talk", endpoint_talk, methods=["POST"]),
        Route("/api/rpm", endpoint_get_rpm, methods=["GET"]),
        Route("/api/models", endpoint_get_models, methods=["GET"]),
        Route("/api/exit", endpoint_exit, methods=["POST"]),
        Route("/api/create_clip", endpoint_create_clip, methods=["POST"]),
        Route("/api/users/search", endpoint_search_users, methods=["GET"]),
        Route(
            "/api/users/{username}/messages",
            endpoint_user_messages,
            methods=["GET"],
        ),
        Route(
            "/api/users/{username}/detail",
            endpoint_get_user_detail,
            methods=["GET"],
        ),
        Route("/api/users", endpoint_list_users, methods=["GET"]),
        Route("/api/chat_accounts", endpoint_get_chat_accounts, methods=["GET"]),
        Route("/api/send_chat_message", endpoint_send_chat_message, methods=["POST"]),
        Route("/api/avatar/{user_id}", endpoint_get_avatar, methods=["GET"]),
        Route("/api/emotes/ffz/{channel_id}", endpoint_get_ffz_emotes, methods=["GET"]),
        Route("/api/moderation/ban", endpoint_moderation_ban, methods=["POST"]),
        Route("/api/moderation/unban", endpoint_moderation_unban, methods=["POST"]),
        Route(
            "/api/moderation/delete_message",
            endpoint_moderation_delete_message,
            methods=["POST"],
        ),
        Route("/api/moderation/purge", endpoint_moderation_purge, methods=["POST"]),
        Route("/api/categories/search", endpoint_search_categories, methods=["GET"]),
        Route("/api/stream/update_info", endpoint_update_stream_info, methods=["POST"]),
        # Analytics REST API
        Route("/api/analytics/overview", endpoint_analytics_overview, methods=["GET"]),
        Route(
            "/api/analytics/chat_activity",
            endpoint_analytics_chat_activity,
            methods=["GET"],
        ),
        Route(
            "/api/analytics/top_chatters",
            endpoint_analytics_top_chatters,
            methods=["GET"],
        ),
        Route(
            "/api/analytics/followers_growth",
            endpoint_analytics_followers_growth,
            methods=["GET"],
        ),
        Route(
            "/api/analytics/viewers_timeline",
            endpoint_analytics_viewers_timeline,
            methods=["GET"],
        ),
        Route(
            "/api/analytics/stream_events",
            endpoint_analytics_stream_events,
            methods=["GET"],
        ),
        Route(
            "/api/analytics/stream_sessions",
            endpoint_analytics_stream_sessions,
            methods=["GET"],
        ),
        # Archivos estáticos (CSS, JS, vendor, icons, manifest, sw.js)
        Mount("/static", NoCacheStaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]

    @asynccontextmanager
    async def lifespan(app_instance: Starlette) -> AsyncGenerator[None]:
        task = asyncio.create_task(_watch_static_files(ws_manager))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await ws_manager.close_all()

    app = Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=[
            Middleware(SecurityHeadersMiddleware),
            Middleware(GZipMiddleware, minimum_size=500, compresslevel=5),
        ],
    )

    # Inyectar dependencias via app.state
    app.state.bot = bot
    app.state.agent = agent
    app.state.event_bus = event_bus
    app.state.ws_manager = ws_manager

    LOGGER.info("Servidor web disponible en http://0.0.0.0:%d", WEB_PORT)
    return app


async def _watch_static_files(ws_manager: WebSocketManager) -> None:
    """Vigila los archivos estáticos en desarrollo y emite live reload por WebSocket."""
    try:
        from watchfiles import awatch
    except ImportError:
        LOGGER.debug("watchfiles no disponible; live reload desactivado")
        return

    LOGGER.info("Live reload activo: vigilando %s", STATIC_DIR)
    try:
        async for changes in awatch(STATIC_DIR):
            LOGGER.info(
                "Cambios detectados en frontend (%d). Notificando...",
                len(changes),
            )
            await ws_manager.broadcast_dev_reload()
    except asyncio.CancelledError:
        pass
    except Exception:
        LOGGER.exception("Error en el watcher de archivos estáticos")
