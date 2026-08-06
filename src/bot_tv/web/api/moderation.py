"""Endpoints de la API REST para acciones de moderación de chat."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from bot_tv.actions.moderation import (
    action_ban_user,
    action_delete_messages,
    action_purge_user,
    action_unban_user,
)
from bot_tv.web.api.helpers import _err, _ok, _parse_body

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def endpoint_moderation_ban(request: Request) -> Response:
    """Endpoint POST /api/moderation/ban."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    reason = body.get("reason", "").strip() or None

    if not username:
        return _err("Campo 'username' requerido.")

    res = await action_ban_user(bot, username, reason=reason)
    if not res.ok:
        return _err(res.error or "No se pudo banear al usuario.")

    return _ok({"username": res.target_username, "banned": True, "reason": reason})


async def endpoint_moderation_unban(request: Request) -> Response:
    """Endpoint POST /api/moderation/unban."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()

    if not username:
        return _err("Campo 'username' requerido.")

    res = await action_unban_user(bot, username)
    if not res.ok:
        return _err(res.error or "No se pudo desbanear al usuario.")

    return _ok({"username": res.target_username, "unbanned": True})


async def endpoint_moderation_delete_message(request: Request) -> Response:
    """Endpoint POST /api/moderation/delete_message."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    message_id = body.get("message_id", "").strip() or None

    res = await action_delete_messages(bot, username, message_id=message_id)
    if not res.ok:
        return _err(res.error or "No se pudo eliminar el mensaje.")

    return _ok(
        {
            "username": res.target_username,
            "message_id": message_id,
            "cleared_all": message_id is None,
        }
    )


async def endpoint_moderation_purge(request: Request) -> Response:
    """Endpoint POST /api/moderation/purge."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()

    if not username:
        return _err("Campo 'username' requerido.")

    res = await action_purge_user(bot, username)
    if not res.ok:
        return _err(res.error or "No se pudo purgar al usuario.")

    return _ok({"username": res.target_username, "purged": True})
