from __future__ import annotations

import logging

import requests

LOGGER = logging.getLogger(__name__)


def check_twitch_connection(retries: int = 3, timeout: float = 5.0) -> bool:
    """Verifica si la API de Twitch (id.twitch.tv) es accesible."""
    import time

    for attempt in range(1, retries + 1):
        try:
            # Usar HEAD para evitar descargar el cuerpo de la respuesta
            requests.head("https://id.twitch.tv/oauth2/validate", timeout=timeout)
            return True
        except requests.RequestException as e:
            LOGGER.warning(
                "Intento %d/%d de conexión con Twitch falló: %s",
                attempt,
                retries,
                e,
            )
            if attempt < retries:
                time.sleep(1.0)

    LOGGER.error("No se pudo conectar con Twitch tras %d intentos.", retries)
    return False


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:  # noqa: S104
    """Verifica si un puerto local ya está siendo utilizado por otro proceso."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def get_port_process_info(port: int) -> tuple[int, str] | None:
    """Obtiene el PID y el nombre del proceso que ocupa un puerto local."""
    import subprocess
    import sys

    if sys.platform == "win32":
        try:
            cmd = f"netstat -ano | findstr :{port}"
            output = subprocess.check_output(cmd, shell=True, text=True)  # noqa: S602
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and f":{port}" in parts[1]:
                    pid = int(parts[-1])
                    if pid > 0:
                        name = _get_process_name_by_pid(pid)
                        return pid, name
        except Exception:
            return None
    return None


def _get_process_name_by_pid(pid: int) -> str:
    import contextlib
    import subprocess

    with contextlib.suppress(Exception):
        cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
        output = subprocess.check_output(cmd, shell=True, text=True)  # noqa: S602
        if output and "," in output:
            return output.split(",")[0].strip('"')
    return "Desconocido"
