"""Endpoints de la API REST relativos al sistema y clips."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from bot_tv.actions.system import action_create_clip, action_exit
from bot_tv.web.api.helpers import _err, _ok

if TYPE_CHECKING:
    from bot_tv.bot import Bot
    from bot_tv.web.ws_handler import WebSocketManager

LOGGER = logging.getLogger(__name__)


async def endpoint_exit(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    LOGGER.info("Apagando bot via API web...")
    response = _ok({"message": "Apagando bot..."})
    response.headers["Connection"] = "close"

    async def shutdown_task() -> None:
        await asyncio.sleep(0.3)
        ws_manager: WebSocketManager | None = getattr(
            request.app.state, "ws_manager", None
        )
        if ws_manager is not None:
            await ws_manager.close_all()

        server = getattr(request.app.state, "server", None)
        if server is not None:
            server.should_exit = True
            await asyncio.sleep(0.25)
            # En Windows con TLS/HTTPS, transport.close() en conexiones keep-alive
            # inactivas puede retener la conexión en server_state.connections
            # esperando close_notify del navegador e impedir lifespan.shutdown().
            server_state = getattr(server, "server_state", None)
            if server_state is not None:
                for conn in list(getattr(server_state, "connections", ())):
                    transport = getattr(conn, "transport", None)
                    if transport is not None:
                        with contextlib.suppress(Exception):
                            transport.abort()
                with contextlib.suppress(Exception):
                    server_state.connections.clear()

        await action_exit(bot)

    task = asyncio.create_task(shutdown_task())
    task.add_done_callback(lambda _: None)
    return response


async def endpoint_create_clip(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    result = await action_create_clip(bot)
    if isinstance(result, str):
        return _err(result)
    return _ok({"url": result.url, "broadcaster_name": result.broadcaster_name})
