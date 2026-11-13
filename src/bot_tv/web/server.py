"""App Starlette: monta el servidor web, WebSocket y la REST API."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import logging
import re
import shutil
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlparse

from starlette.applications import Starlette
from starlette.datastructures import Headers, MutableHeaders, QueryParams
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send
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
    endpoint_analytics_followers_events,
    endpoint_analytics_followers_growth,
    endpoint_analytics_messages,
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
INVALID_HOST_MSG = "Cabecera Host inválida o no autorizada."
AUTH_COOKIE_NAME = "bot_tv_token"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
REVALIDATE_HEADERS = {"Cache-Control": "no-cache"}
VITE_DEV_PORT = 5173
PUBLIC_EXEMPT_METHODS = frozenset({"GET", "HEAD"})
PUBLIC_EXEMPT_EXACT_PATHS = frozenset(
    {"/api/health", "/manifest.json", "/sw.js", "/favicon.ico"}
)
PUBLIC_EXEMPT_PREFIXES = ("/icons/", "/static/icons/")
VITE_MANIFEST_PATH_RE = re.compile(r"^/static/assets/manifest-[A-Za-z0-9_-]+\.json$")
_HOST_FORBIDDEN_CHARS = frozenset(" \t\r\n/@\\?#;,")
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")
_LOCALHOST_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
_LOCAL_DOMAIN_SUFFIXES = (".local", ".lan", ".home", ".internal", ".ts.net")

CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' https://embed.twitch.tv https://player.twitch.tv; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
    "https://cdnjs.cloudflare.com; "
    "img-src 'self' data: blob: https://static-cdn.jtvnw.net https://*.jtvnw.net "
    "https://cdn.frankerfacez.com https://cdn.betterttv.net; "
    "connect-src 'self' ws: wss: https://api.frankerfacez.com "
    "https://api.betterttv.net; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
    "frame-src 'self' https://player.twitch.tv https://embed.twitch.tv; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self';"
)


def _expected_access_token() -> str:
    return WEB_ACCESS_TOKEN.strip()


def _apply_security_headers(headers: MutableHeaders) -> None:
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "SAMEORIGIN"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    headers["Content-Security-Policy"] = CSP_HEADER
    if IS_PRODUCTION:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"


def is_authorized_request(
    headers: object,
    cookies: Mapping[str, str],
    query_token: str = "",
) -> bool:
    """Verifica el token de acceso si WEB_ACCESS_TOKEN está configurado."""
    expected = _expected_access_token()
    if not expected:
        return True

    # 1. Cookie de sesión
    cookie_val = cookies.get(AUTH_COOKIE_NAME, "").strip()
    if cookie_val and hmac.compare_digest(cookie_val, expected):
        return True

    # 2. Query param (?token=...)
    cleaned_query = query_token.strip()
    if cleaned_query and hmac.compare_digest(cleaned_query, expected):
        return True

    # 3. Cabeceras Authorization / X-Access-Token
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        auth_header = str(get_header("authorization", "") or "")
        if auth_header.lower().startswith("bearer "):
            bearer_val = auth_header[7:].strip()
            if bearer_val and hmac.compare_digest(bearer_val, expected):
                return True
        x_token = str(get_header("x-access-token", "") or "").strip()
        if x_token and hmac.compare_digest(x_token, expected):
            return True

    return False


def _is_public_exempt_request(method: str, path: str) -> bool:
    """Permite únicamente endpoints/assets públicos para health e instalación PWA."""
    if method.upper() not in PUBLIC_EXEMPT_METHODS:
        return False
    if ".." in path or "\\" in path:
        return False
    if path in PUBLIC_EXEMPT_EXACT_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in PUBLIC_EXEMPT_PREFIXES):
        return True
    return bool(VITE_MANIFEST_PATH_RE.fullmatch(path))


def _build_clean_redirect_url(path: str, raw_query_string: bytes) -> str:
    """Elimina ?token= de la URL para evitar credenciales en historial del navegador."""
    normalized_path = path.replace("\\", "/")
    safe_path = (
        normalized_path
        if normalized_path.startswith("/") and not normalized_path.startswith("//")
        else f"/{normalized_path.lstrip('/')}"
    )
    raw_qs = raw_query_string.decode("latin-1")
    filtered_params = [
        (key, value)
        for key, value in parse_qsl(raw_qs, keep_blank_values=True)
        if key != "token"
    ]
    clean_query = urlencode(filtered_params)
    return f"{safe_path}?{clean_query}" if clean_query else safe_path


def _parse_netloc(raw_value: str) -> tuple[str, int | None] | None:
    """Valida sintácticamente una cabecera Host y retorna (hostname, puerto)."""
    value = raw_value.strip()
    if not value or any(ch in _HOST_FORBIDDEN_CHARS for ch in value):
        return None
    parsed = urlparse(f"http://{value}")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or not parsed.hostname
    ):
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is not None and not (1 <= port <= 65535):
        return None
    return parsed.hostname.lower(), port


def _parse_origin_url(raw_origin: str) -> tuple[str, str, int | None] | None:
    """Parsea una cabecera Origin estrictamente; rechaza 'null' y formas inválidas."""
    origin = raw_origin.strip()
    if not origin or origin.lower() == "null":
        return None
    parsed = urlparse(origin)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not parsed.hostname
    ):
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is not None and not (1 <= port <= 65535):
        return None
    return scheme, parsed.hostname.lower(), port


def _cors_origin_tuples(
    cors_origins: frozenset[str] | None = None,
) -> set[tuple[str, str, int]]:
    allowed: set[tuple[str, str, int]] = set()
    active_origins = CORS_ORIGINS if cors_origins is None else cors_origins
    for raw in active_origins:
        parsed = _parse_origin_url(raw)
        if parsed is None:
            continue
        scheme, hostname, port = parsed
        eff_port = port or (443 if scheme == "https" else 80)
        allowed.add((scheme, hostname, eff_port))
    return allowed


def _cors_hostnames(cors_origins: frozenset[str] | None = None) -> set[str]:
    hosts: set[str] = set()
    active_origins = CORS_ORIGINS if cors_origins is None else cors_origins
    for raw in active_origins:
        parsed = _parse_origin_url(raw)
        if parsed is not None:
            hosts.add(parsed[1])
    return hosts


def _is_local_or_lan_hostname(hostname: str) -> bool:
    norm = hostname.rstrip(".").lower()
    if not norm:
        return False
    if norm in _LOCALHOST_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(norm)
    except ValueError:
        return "." not in norm or norm.endswith(_LOCAL_DOMAIN_SUFFIXES)

    mapped = getattr(ip, "ipv4_mapped", None)
    target_ip = mapped if mapped is not None else ip
    return (
        target_ip.is_loopback
        or target_ip.is_private
        or target_ip.is_link_local
        or (target_ip.version == 4 and target_ip in _CGNAT_NETWORK)
    )


def _is_unspecified_ip(hostname: str) -> bool:
    try:
        return ipaddress.ip_address(hostname).is_unspecified
    except ValueError:
        return False


def is_valid_host_header(
    raw_host: str,
    scope: Scope | None = None,
    cors_origins: frozenset[str] | None = None,
) -> bool:
    """Valida Host sintácticamente y por origen permitido (sin proxy ciego)."""
    parsed = _parse_netloc(raw_host)
    if parsed is None:
        return False
    hostname, _ = parsed

    if scope is not None:
        server = scope.get("server")
        if (
            isinstance(server, (tuple, list))
            and server
            and isinstance(server[0], str)
            and hostname == server[0].lower()
        ):
            return True

    if hostname in _LOCALHOST_HOSTNAMES:
        return True
    if WEB_HOST and hostname == WEB_HOST.lower() and not _is_unspecified_ip(hostname):
        return True
    if hostname in _cors_hostnames(cors_origins):
        return True
    return _is_local_or_lan_hostname(hostname)


def is_allowed_request_origin(
    headers: Headers,
    scope: Scope,
    cors_origins: frozenset[str] | None = None,
) -> bool:
    """Valida Origin y Sec-Fetch-Site frente al Host real del servidor."""
    origin_values = headers.getlist("origin")
    if len(origin_values) > 1:
        return False

    origin = origin_values[0] if origin_values else None
    sec_fetch_site = headers.get("sec-fetch-site", "").strip().lower()

    parsed_origin: tuple[str, str, int | None] | None = None
    if origin is not None:
        parsed_origin = _parse_origin_url(origin)
        if parsed_origin is None:
            return False
        o_scheme, o_host, o_port = parsed_origin
        o_eff_port = o_port or (443 if o_scheme == "https" else 80)
        if (o_scheme, o_host, o_eff_port) in _cors_origin_tuples(cors_origins):
            return True
    else:
        o_scheme = ""
        o_host = ""
        o_port = None
        o_eff_port = 0

    if sec_fetch_site and sec_fetch_site not in ALLOWED_FETCH_SITES:
        allow_dev_vite_samesite = (
            IS_DEV
            and sec_fetch_site == "same-site"
            and parsed_origin is not None
            and o_port == VITE_DEV_PORT
            and _is_local_or_lan_hostname(o_host)
        )
        if not allow_dev_vite_samesite:
            return False

    if parsed_origin is None:
        return True

    host_values = headers.getlist("host")
    if len(host_values) != 1 or not is_valid_host_header(
        host_values[0], scope, cors_origins=cors_origins
    ):
        return False

    parsed_host = _parse_netloc(host_values[0])
    if parsed_host is None:
        return False
    h_host, h_port = parsed_host

    req_scheme = str(scope.get("scheme", "http")).lower()
    req_is_https = req_scheme in {"https", "wss"}
    if req_is_https and o_scheme != "https":
        return False

    # Reverse proxy TLS (p. ej. Tailscale Serve) puede reenviar HTTP local sin puerto
    if o_scheme == "https" and not req_is_https and h_port is None and o_port is None:
        ports_match = True
    else:
        h_eff_port = h_port or (443 if req_is_https else 80)
        ports_match = h_eff_port == o_eff_port

    if o_host == h_host and ports_match:
        return True

    if IS_DEV and _is_local_or_lan_hostname(o_host):
        if o_port == VITE_DEV_PORT:
            return True
        if (
            o_host in _LOCALHOST_HOSTNAMES
            and h_host in _LOCALHOST_HOSTNAMES
            and ports_match
        ):
            return True

    return False


class SecurityHeadersMiddleware:
    """Middleware ASGI puro para auth, validación Host/Origin y cabeceras seguras."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                resp_headers = MutableHeaders(scope=message)
                _apply_security_headers(resp_headers)
            await send(message)

        headers = Headers(scope=scope)
        method = str(scope.get("method", "GET")).upper()
        path = str(scope.get("path", "/"))

        host_values = headers.getlist("host")
        if len(host_values) != 1 or not is_valid_host_header(host_values[0], scope):
            invalid_host_resp = JSONResponse(
                {"ok": False, "error": INVALID_HOST_MSG},
                status_code=400,
            )
            await invalid_host_resp(scope, receive, send_with_security_headers)
            return

        expected_token = _expected_access_token()
        if expected_token and not _is_public_exempt_request(method, path):
            cookies = HTTPConnection(scope).cookies
            query_params = QueryParams(scope.get("query_string", b""))
            query_token = query_params.get("token", "").strip()
            if not is_authorized_request(headers, cookies, query_token=query_token):
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
                await unauth_resp(scope, receive, send_with_security_headers)
                return

            if (
                method == "GET"
                and query_token
                and hmac.compare_digest(query_token, expected_token)
            ):
                clean_url = _build_clean_redirect_url(
                    path, scope.get("query_string", b"")
                )
                redirect_resp = RedirectResponse(
                    url=clean_url,
                    status_code=302,
                    headers={"Cache-Control": "no-store"},
                )
                redirect_resp.set_cookie(
                    key=AUTH_COOKIE_NAME,
                    value=expected_token,
                    httponly=True,
                    secure=str(scope.get("scheme", "http")).lower() == "https",
                    samesite="lax",
                    path="/",
                    max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
                )
                await redirect_resp(scope, receive, send_with_security_headers)
                return

        if method in MUTATING_METHODS and not is_allowed_request_origin(headers, scope):
            blocked_resp = JSONResponse(
                {"ok": False, "error": CROSS_ORIGIN_BLOCKED_MSG},
                status_code=403,
            )
            await blocked_resp(scope, receive, send_with_security_headers)
            return

        await self.app(scope, receive, send_with_security_headers)


def _ensure_frontend_dist() -> Path:
    """Verifica el bundle compilado en DIST_DIR sin bloquear el arranque ASGI."""
    if (DIST_DIR / "index.html").exists():
        return DIST_DIR

    LOGGER.warning(
        "Bundle frontend no encontrado en %s; usando %s. "
        "Ejecuta 'pnpm run build' para compilar o 'pnpm run dev' en desarrollo.",
        DIST_DIR,
        STATIC_DIR,
    )
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

    # no-cache fuerza revalidar: evita un index.html viejo que apunte a bundles borrados
    def revalidated_file(filename: str) -> Callable[[Request], Response]:
        def handler(request: Request) -> Response:
            return FileResponse(web_root / filename, headers=REVALIDATE_HEADERS)

        return handler

    homepage = revalidated_file("index.html")

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
        Route("/sw.js", revalidated_file("sw.js")),
        Route("/manifest.json", revalidated_file("manifest.json")),
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
        Route("/api/analytics/messages", endpoint_analytics_messages, methods=["GET"]),
        Route(
            "/api/analytics/followers_events",
            endpoint_analytics_followers_events,
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
