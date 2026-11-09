"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
import shutil
import subprocess
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

from bot_tv.utils.env import (
    APP_ENV,
    CORS_ORIGINS,
    IDLE_SHUTDOWN_SECONDS,
    IS_DEV,
    IS_PRODUCTION,
    MAX_WS_CLIENTS,
    WEB_ACCESS_TOKEN,
    WEB_HOST,
    WEB_PORT,
)
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
DIST_DIR = Path(__file__).parent / "dist"
PROJECT_ROOT = Path(__file__).resolve().parents[3]

MUTATING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})
CROSS_ORIGIN_BLOCKED_MSG = "Solicitud cross-origin bloqueada."
AUTH_COOKIE_NAME = "bot_tv_token"

CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' https://embed.twitch.tv https://player.twitch.tv; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
    "https://cdnjs.cloudflare.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self' ws: wss: https:; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "frame-src 'self' https://player.twitch.tv https://embed.twitch.tv; "
    "frame-ancestors 'self';"
)


def _apply_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = CSP_HEADER
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )


def is_authorized_request(
    headers: dict[str, str] | object,
    cookies: dict[str, str],
    query_token: str = "",
) -> bool:
    """Verifica el token de acceso si WEB_ACCESS_TOKEN está configurado."""
    if not WEB_ACCESS_TOKEN:
        return True

    expected = WEB_ACCESS_TOKEN.strip()
    if not expected:
        return True

    # 1. Cookie de sesión
    cookie_val = cookies.get(AUTH_COOKIE_NAME, "")
    if cookie_val and hmac.compare_digest(cookie_val, expected):
        return True

    # 2. Query param (?token=...)
    if query_token and hmac.compare_digest(query_token, expected):
        return True

    # 3. Cabeceras Authorization / X-Access-Token
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        auth_header = str(get_header("authorization", "") or "")
        if auth_header.lower().startswith("bearer "):
            bearer_val = auth_header[7:].strip()
            if hmac.compare_digest(bearer_val, expected):
                return True
        x_token = str(get_header("x-access-token", "") or "").strip()
        if x_token and hmac.compare_digest(x_token, expected):
            return True

    return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Valida Same-Origin en mutaciones, acceso opcional por token y cabeceras."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Verificar WEB_ACCESS_TOKEN si está configurado (excepto /api/health)
        if WEB_ACCESS_TOKEN and path != "/api/health":
            query_token = request.query_params.get("token", "").strip()
            if not is_authorized_request(
                request.headers, request.cookies, query_token=query_token
            ):
                unauth_resp = JSONResponse(
                    {
                        "ok": False,
                        "error": (
                            "No autorizado. Añade ?token=TU_WEB_ACCESS_TOKEN "
                            "al abrir el dashboard."
                        ),
                    },
                    status_code=401,
                )
                _apply_security_headers(unauth_resp)
                return unauth_resp

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
            if origin and origin not in CORS_ORIGINS:
                origin_host = urlparse(origin).netloc
                host = request.headers.get("x-forwarded-host") or request.headers.get(
                    "host", ""
                )
                if origin_host and host and origin_host != host:
                    blocked_resp = JSONResponse(
                        {"ok": False, "error": CROSS_ORIGIN_BLOCKED_MSG},
                        status_code=403,
                    )
                    _apply_security_headers(blocked_resp)
                    return blocked_resp

        response = await call_next(request)
        _apply_security_headers(response)

        # Persistir cookie HttpOnly si el usuario ingresó con ?token=...
        if WEB_ACCESS_TOKEN:
            query_token = request.query_params.get("token", "").strip()
            if query_token and hmac.compare_digest(
                query_token, WEB_ACCESS_TOKEN.strip()
            ):
                response.set_cookie(
                    key=AUTH_COOKIE_NAME,
                    value=WEB_ACCESS_TOKEN.strip(),
                    httponly=True,
                    secure=IS_PRODUCTION,
                    samesite="lax",
                    max_age=60 * 60 * 24 * 30,
                )

        return response


def _ensure_frontend_dist() -> Path:
    """Garantiza que exista el bundle compilado por Vite en DIST_DIR."""
    if (DIST_DIR / "index.html").exists():
        return DIST_DIR

    pnpm_bin = shutil.which("pnpm")
    if pnpm_bin and (PROJECT_ROOT / "vite.config.js").exists():
        LOGGER.info("Compilando bundle frontend con Vite...")
        try:
            subprocess.run(  # noqa: S603
                [pnpm_bin, "run", "build"],
                cwd=str(PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
            )
            if (DIST_DIR / "index.html").exists():
                return DIST_DIR
        except Exception:
            LOGGER.exception("Fallo al compilar frontend con Vite; usando STATIC_DIR")

    return STATIC_DIR


class SmartCacheStaticFiles(StaticFiles):
    """Aplica caché inmutable a bundles con hash de Vite y control por entorno."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        norm_path = path.replace("\\", "/").lstrip("/")
        if norm_path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif norm_path.startswith("icons/"):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        elif IS_PRODUCTION:
            response.headers["Cache-Control"] = (
                "public, max-age=3600, stale-while-revalidate=86400"
            )
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


def create_app(bot: Bot, agent: TalkAgent, event_bus: EventBus) -> Starlette:
    """Crea y configura la aplicación Starlette con todos los endpoints."""
    ws_manager = WebSocketManager(event_bus, bot)
    ws_manager.register()
    web_root = _ensure_frontend_dist()

    async def homepage(request: Request) -> Response:
        return FileResponse(web_root / "index.html")

    async def healthcheck(request: Request) -> Response:
        return JSONResponse(
            {
                "ok": True,
                "status": "healthy",
                "env": APP_ENV,
                "ws_clients": len(ws_manager._connections),
                "max_ws_clients": MAX_WS_CLIENTS,
                "idle_shutdown_seconds": IDLE_SHUTDOWN_SECONDS,
            }
        )

    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws_manager.handle(ws)

    routes = [
        Route("/", homepage),
        Route("/api/health", healthcheck, methods=["GET"]),
        Route("/sw.js", lambda r: FileResponse(web_root / "sw.js")),
        Route("/manifest.json", lambda r: FileResponse(web_root / "manifest.json")),
        Route(
            "/favicon.ico",
            lambda r: FileResponse(web_root / "icons" / "icon-192.png"),
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
        # Bundle y recursos estáticos servidos desde dist/ (compilado por Vite)
        Mount(
            "/static",
            SmartCacheStaticFiles(directory=str(web_root)),
            name="static",
        ),
    ]

    @asynccontextmanager
    async def lifespan(app_instance: Starlette) -> AsyncGenerator[None]:
        task = asyncio.create_task(_watch_static_files(ws_manager)) if IS_DEV else None
        try:
            yield
        finally:
            if task is not None:
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

    LOGGER.info("Servidor web disponible en http://%s:%d", WEB_HOST, WEB_PORT)
    return app


async def _rebuild_vite_bundle() -> bool:
    """Ejecuta `pnpm run build` de forma asíncrona cuando cambian archivos en dev."""
    pnpm_bin = shutil.which("pnpm")
    if not pnpm_bin or not (PROJECT_ROOT / "vite.config.js").exists():
        return True
    try:
        proc = await asyncio.create_subprocess_exec(
            pnpm_bin,
            "run",
            "build",
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            LOGGER.error(
                "Error al recompilar con Vite: %s",
                stderr.decode("utf-8", errors="replace"),
            )
            return False
        return True
    except Exception:
        LOGGER.exception("Error ejecutando build de Vite en segundo plano")
        return False


async def _watch_static_files(ws_manager: WebSocketManager) -> None:
    """Vigila STATIC_DIR en desarrollo, recompila con Vite y emite live reload."""
    try:
        from watchfiles import awatch
    except ImportError:
        LOGGER.debug("watchfiles no disponible; live reload desactivado")
        return

    LOGGER.info("Live reload + Vite build activo: vigilando %s", STATIC_DIR)
    try:
        async for changes in awatch(STATIC_DIR):
            LOGGER.info(
                "Cambios detectados en frontend (%d). Recompilando con Vite...",
                len(changes),
            )
            if await _rebuild_vite_bundle():
                await ws_manager.broadcast_dev_reload()
    except asyncio.CancelledError:
        pass
    except Exception:
        LOGGER.exception("Error en el watcher de archivos estáticos")
