"""Endpoints de la API REST relativos al sistema y clips."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from bot_tv.actions.system import action_create_clip, action_exit
from bot_tv.web.api.helpers import _err, _ok

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def endpoint_exit(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    LOGGER.info("Apagando bot via API web...")
    response = _ok({"message": "Apagando bot..."})

    async def shutdown_task() -> None:
        await asyncio.sleep(0.5)
        server = getattr(request.app.state, "server", None)
        if server:
            server.should_exit = True
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
