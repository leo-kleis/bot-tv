from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import subprocess
import sys

import httpx

LOGGER = logging.getLogger(__name__)

_TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
_RETRY_DELAY_SECONDS = 1.0
_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
_HTTP_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30.0,
)

_http_client: httpx.AsyncClient | None = None


def init_http_client() -> httpx.AsyncClient:
    """Inicializa y retorna el cliente httpx.AsyncClient compartido."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            limits=_HTTP_LIMITS,
        )
    return _http_client


def get_http_client() -> httpx.AsyncClient:
    """Retorna el cliente httpx.AsyncClient compartido, creándolo si hace falta."""
    return init_http_client()


async def close_http_client() -> None:
    """Cierra el cliente HTTP compartido de forma segura e idempotente."""
    global _http_client
    client = _http_client
    _http_client = None
    if client is not None and not client.is_closed:
        await client.aclose()


async def check_twitch_connection(retries: int = 3, timeout: float = 5.0) -> bool:
    """Verifica si la API de Twitch (id.twitch.tv) es accesible."""
    client = get_http_client()
    for attempt in range(1, retries + 1):
        try:
            # Usar HEAD para evitar descargar el cuerpo de la respuesta
            await client.head(_TWITCH_VALIDATE_URL, timeout=timeout)
            return True
        except (TimeoutError, httpx.HTTPError) as e:
            LOGGER.warning(
                "Intento %d/%d de conexión con Twitch falló: %s",
                attempt,
                retries,
                e,
            )
            if attempt < retries:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)

    LOGGER.error("No se pudo conectar con Twitch tras %d intentos.", retries)
    return False


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:  # noqa: S104
    """Verifica si un puerto local ya está siendo utilizado por otro proceso."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def get_port_process_info(port: int) -> tuple[int, str] | None:
    """Obtiene el PID y el nombre del proceso que ocupa un puerto local."""
    if sys.platform == "win32":
        try:
            cmd = ["netstat", "-ano"]
            output = subprocess.check_output(cmd, text=True)  # noqa: S603
            for line in output.strip().splitlines():
                if f":{port}" not in line:
                    continue
                parts = line.split()
                if len(parts) >= 5 and f":{port}" in parts[1]:
                    pid = int(parts[-1])
                    if pid > 0:
                        name = _get_process_name_by_pid(pid)
                        return pid, name
        except subprocess.SubprocessError, ValueError, OSError:
            return None
    return None


def _get_process_name_by_pid(pid: int) -> str:
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        cmd = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
        output = subprocess.check_output(cmd, text=True)  # noqa: S603
        if output and "," in output:
            return output.split(",")[0].strip('"')
    return "Desconocido"
