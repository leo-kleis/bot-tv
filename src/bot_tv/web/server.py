"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import logging
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
    endpoint_create_clip,
    endpoint_exit,
    endpoint_get_models,
    endpoint_get_rpm,
    endpoint_search_users,
    endpoint_set_nickname,
    endpoint_switch_model,
    endpoint_sync_followers,
    endpoint_talk,
    endpoint_toggle_bot,
)
from bot_tv.web.ws_handler import WebSocketManager

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot
    from bot_tv.event_bus import EventBus

LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

WEB_PORT = 8080


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
        Route("/api/toggle_bot", endpoint_toggle_bot, methods=["POST"]),
        Route("/api/set_nickname", endpoint_set_nickname, methods=["POST"]),
        Route("/api/switch_model", endpoint_switch_model, methods=["POST"]),
        Route("/api/talk", endpoint_talk, methods=["POST"]),
        Route("/api/rpm", endpoint_get_rpm, methods=["GET"]),
        Route("/api/models", endpoint_get_models, methods=["GET"]),
        Route("/api/exit", endpoint_exit, methods=["POST"]),
        Route("/api/create_clip", endpoint_create_clip, methods=["POST"]),
        Route("/api/users/search", endpoint_search_users, methods=["GET"]),
        # Archivos estáticos (CSS, JS, vendor, icons, manifest, sw.js)
        Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]

    app = Starlette(
        routes=routes,
        middleware=[Middleware(GZipMiddleware, minimum_size=500, compresslevel=5)],
    )

    # Inyectar dependencias via app.state
    app.state.bot = bot
    app.state.agent = agent
    app.state.event_bus = event_bus

    LOGGER.info("Servidor web disponible en http://0.0.0.0:%d", WEB_PORT)
    return app
