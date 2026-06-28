"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import hashlib
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
    endpoint_get_chat_accounts,
    endpoint_get_models,
    endpoint_get_rpm,
    endpoint_list_users,
    endpoint_search_users,
    endpoint_send_chat_message,
    endpoint_set_nickname,
    endpoint_switch_model,
    endpoint_sync_followers,
    endpoint_sync_user_roles,
    endpoint_talk,
    endpoint_toggle_bot,
    endpoint_update_user_roles,
)
from bot_tv.web.ws_handler import WebSocketManager

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot
    from bot_tv.event_bus import EventBus

LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

WEB_PORT = 8080


def _compute_static_hash() -> str:
    """Genera un hash corto basado en el contenido de todos los archivos estáticos.

    Recorre recursivamente STATIC_DIR, ordena los archivos por ruta relativa
    para determinismo, y calcula un MD5 combinado. Retorna los primeros 8
    caracteres del hash hexadecimal.
    """
    hasher = hashlib.md5()  # noqa: S324 — no se usa para seguridad
    for file_path in sorted(STATIC_DIR.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(STATIC_DIR).as_posix()
            hasher.update(rel.encode())
            hasher.update(file_path.read_bytes())
    return hasher.hexdigest()[:8]


def create_app(bot: Bot, agent: TalkAgent, event_bus: EventBus) -> Starlette:
    """Crea y configura la aplicación Starlette con todos los endpoints."""
    static_hash = _compute_static_hash()
    sw_template = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    sw_body = sw_template.replace("__CACHE_VERSION__", f"bot-tv-{static_hash}")
    LOGGER.info("Hash de archivos estáticos: %s", static_hash)

    ws_manager = WebSocketManager(event_bus, bot)
    ws_manager.register()

    async def homepage(request: Request) -> Response:
        return FileResponse(STATIC_DIR / "index.html")

    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws_manager.handle(ws)

    routes = [
        Route("/", homepage),
        Route(
            "/sw.js",
            lambda r: Response(
                sw_body,
                media_type="application/javascript",
                headers={"Cache-Control": "no-cache"},
            ),
        ),
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
        Route("/api/update_user_roles", endpoint_update_user_roles, methods=["POST"]),
        Route("/api/sync_user_roles", endpoint_sync_user_roles, methods=["POST"]),
        Route("/api/switch_model", endpoint_switch_model, methods=["POST"]),
        Route("/api/talk", endpoint_talk, methods=["POST"]),
        Route("/api/rpm", endpoint_get_rpm, methods=["GET"]),
        Route("/api/models", endpoint_get_models, methods=["GET"]),
        Route("/api/exit", endpoint_exit, methods=["POST"]),
        Route("/api/create_clip", endpoint_create_clip, methods=["POST"]),
        Route("/api/users/search", endpoint_search_users, methods=["GET"]),
        Route("/api/users", endpoint_list_users, methods=["GET"]),
        Route("/api/chat_accounts", endpoint_get_chat_accounts, methods=["GET"]),
        Route("/api/send_chat_message", endpoint_send_chat_message, methods=["POST"]),
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
