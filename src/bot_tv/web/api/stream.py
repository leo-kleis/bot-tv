"""Endpoints de la API REST para búsqueda de categorías y actualización de stream."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from bot_tv.actions.stream import action_search_categories, action_update_channel_info
from bot_tv.web.api.helpers import _err, _ok, _parse_body

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def endpoint_search_categories(request: Request) -> Response:
    """Endpoint GET /api/categories/search?query=..."""
    bot: Bot = request.app.state.bot
    query = request.query_params.get("query", "").strip()
    if not query:
        return _ok({"categories": []})

    categories = await action_search_categories(bot, query)
    return _ok({"categories": categories})


async def endpoint_update_stream_info(request: Request) -> Response:
    """Endpoint POST /api/stream/update_info."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)

    title = body.get("title")
    category_id = body.get("category_id")

    if title is None and category_id is None:
        return _err("Debe enviar al menos 'title' o 'category_id'.")

    result = await action_update_channel_info(
        bot,
        title=str(title) if title is not None else None,
        category_id=str(category_id) if category_id is not None else None,
    )

    if not result.get("ok"):
        return _err(result.get("error", "Error al actualizar información del canal."))

    return _ok({"updated": True})
