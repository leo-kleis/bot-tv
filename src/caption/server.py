from __future__ import annotations

import asyncio
import contextlib
import logging

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketState

from caption.config import CAPTION_HOST, CAPTION_PORT

LOGGER = logging.getLogger(__name__)


class CaptionServer:
    """Servidor Starlette para emitir transcripciones vía WebSockets a OBS."""

    host: str
    port: int
    active_connections: set[WebSocket]
    _server: uvicorn.Server | None
    _serve_task: asyncio.Task[None] | None
    app: Starlette

    def __init__(self, host: str = CAPTION_HOST, port: int = CAPTION_PORT) -> None:
        self.host = host
        self.port = port
        self.active_connections = set()
        self._server = None
        self._serve_task = None

        # Configuración de Starlette
        self.app = Starlette(
            routes=[
                Route("/health", self.health_endpoint, methods=["GET"]),
                WebSocketRoute("/ws", self.websocket_endpoint),
            ]
        )

    async def health_endpoint(self, request: Request) -> JSONResponse:
        """Endpoint HTTP básico para chequear la salud del servicio."""
        return JSONResponse(
            {
                "status": "healthy",
                "connections": len(self.active_connections),
            }
        )

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        """Maneja las conexiones WebSocket entrantes de OBS."""
        # Validar origen por seguridad básica
        origin = websocket.headers.get("origin", "")
        # OBS cargado localmente (file://) suele enviar origin "null" o no enviarlo.
        # Permitimos localhosts, ips de loopback y "null" para orígenes locales de OBS
        allowed_origins = ("localhost", "127.0.0.1", "null", "")
        if origin and not any(allowed in origin for allowed in allowed_origins):
            LOGGER.warning(
                "Conexión WebSocket rechazada de origen no autorizado: %s",
                origin,
            )
            await websocket.close(code=4003)
            return

        await websocket.accept()
        self.active_connections.add(websocket)
        LOGGER.info(
            "Cliente conectado. Conexiones activas: %d (Origen: %s)",
            len(self.active_connections),
            origin or "Local/OBS",
        )

        try:
            # Mantenemos la conexión viva y procesamos mensajes entrantes si los hubiera
            while True:
                await websocket.receive_text()
        except Exception:
            # Las desconexiones normales o fallas de red entran aquí
            pass
        finally:
            self.active_connections.discard(websocket)
            LOGGER.info(
                "Cliente desconectado. Conexiones activas: %d",
                len(self.active_connections),
            )

    async def broadcast(self, text: str, is_final: bool) -> None:
        """Envía el texto transcrito a todos los clientes WebSocket conectados."""
        if not self.active_connections:
            return

        payload = {"text": text, "is_final": is_final}

        # Copiamos la lista de conexiones para evitar problemas de
        # concurrencia al remover elementos rotos
        dead_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            if connection.client_state == WebSocketState.CONNECTED:
                try:
                    await connection.send_json(payload)
                except Exception:
                    LOGGER.warning(
                        "Fallo al enviar datos a cliente. Marcando para desconexión."
                    )
                    dead_connections.append(connection)
            else:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.active_connections.discard(dead)

    async def start(self) -> None:
        """Inicia el servidor uvicorn en segundo plano."""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            ws_ping_interval=20.0,
            ws_ping_timeout=20.0,
        )
        self._server = uvicorn.Server(config)

        # Ejecutamos el servidor como una tarea asíncrona paralela
        self._serve_task = asyncio.create_task(self._server.serve())
        self._serve_task.add_done_callback(self._serve_task_done_callback)
        LOGGER.info(
            "Servidor WebSocket iniciado en ws://%s:%d/ws",
            self.host,
            self.port,
        )

    def _serve_task_done_callback(self, task: asyncio.Task[None]) -> None:
        """Callback ejecutado cuando la tarea del servidor uvicorn finaliza."""
        try:
            exc = task.exception()
            if exc:
                LOGGER.error("La tarea del servidor uvicorn falló: %s", exc)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Detiene el servidor WebSocket limpiamente."""
        LOGGER.info("Deteniendo servidor WebSocket de subtítulos...")

        # Cerrar todas las conexiones activas
        for connection in list(self.active_connections):
            with contextlib.suppress(Exception):
                await connection.close(code=1000)
        self.active_connections.clear()

        if self._server is not None:
            self._server.should_exit = True

        if self._serve_task is not None:
            # Esperar a que la tarea del servidor finalice (tiempo de gracia)
            try:
                await asyncio.wait_for(self._serve_task, timeout=3.0)
            except TimeoutError:
                LOGGER.warning("El servidor uvicorn no se detuvo a tiempo. Cancelando.")
                self._serve_task.cancel()
            except Exception:
                pass
            finally:
                self._serve_task = None
                self._server = None

        LOGGER.info("Servidor WebSocket detenido.")
