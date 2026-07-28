"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from bot_tv.web.api import (
    endpoint_clear_agent_chat,
    endpoint_create_clip,
    endpoint_exit,
    endpoint_get_avatar,
    endpoint_get_chat_accounts,
    endpoint_get_ffz_emotes,
    endpoint_get_models,
    endpoint_get_rpm,
    endpoint_list_users,
    endpoint_search_users,
    endpoint_send_chat_message,
    endpoint_set_context_limit,
    endpoint_set_nickname,
    endpoint_switch_model,
    endpoint_sync_followers,
    endpoint_sync_user_roles,
    endpoint_talk,
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


class NoCacheStaticFiles(StaticFiles):
    """Evita el almacenamiento en caché del navegador para archivos estáticos."""

    async def get_response(self, path: str, scope: any) -> Response:  # type: ignore[override]

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
        Route("/api/users", endpoint_list_users, methods=["GET"]),
        Route("/api/chat_accounts", endpoint_get_chat_accounts, methods=["GET"]),
        Route("/api/send_chat_message", endpoint_send_chat_message, methods=["POST"]),
        Route("/api/avatar/{user_id}", endpoint_get_avatar, methods=["GET"]),
        Route("/api/emotes/ffz/{channel_id}", endpoint_get_ffz_emotes, methods=["GET"]),
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

    app = Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=[Middleware(GZipMiddleware, minimum_size=500, compresslevel=5)],
    )

    # Inyectar dependencias via app.state
    app.state.bot = bot
    app.state.agent = agent
    app.state.event_bus = event_bus

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
