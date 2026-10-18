"""Endpoints de la API REST relativos al chat y emotes de Twitch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import twitchio
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bot_tv.web.api.helpers import _err, _get_str, _ok, _parse_body

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

MAX_FFZ_CACHE_SIZE = 32
_FFZ_CACHE: dict[str, dict[str, Any]] = {}


async def endpoint_get_chat_accounts(request: Request) -> Response:
    """Retorna las cuentas autenticadas (Bot o Broadcaster) para usar en el chat."""
    bot: Bot = request.app.state.bot
    try:
        tokens_metadata = await bot.token_repo.get_accounts_summary()
        accounts = []
        for row in tokens_metadata:
            user_id = row["user_id"]
            username = row["username"]
            role_type = "bot" if user_id == bot.bot_id else "broadcaster"
            accounts.append(
                {"user_id": user_id, "username": username, "type": role_type}
            )
        return _ok(accounts)
    except Exception as e:
        LOGGER.exception("Error al obtener las cuentas de chat: %s", e)
        return _err("Error interno del servidor al obtener las cuentas.", status=500)


async def endpoint_send_chat_message(request: Request) -> Response:
    """Envía un mensaje de chat desde la cuenta especificada (Bot o Broadcaster)."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    sender_id = _get_str(body, "sender_id")
    message = _get_str(body, "message")

    if not sender_id:
        return _err("Campo 'sender_id' requerido.")
    if not message:
        return _err("Campo 'message' requerido.")

    try:
        # 1. Obtener la información del canal destino (broadcaster)
        # El canal es aquel cuyo user_id != bot_id en tokens
        tokens_metadata = await bot.token_repo.get_accounts_summary()
        broadcaster_accounts = [
            t for t in tokens_metadata if t["user_id"] != bot.bot_id
        ]
        if not broadcaster_accounts:
            return _err("No se encontró el canal (broadcaster) de destino.")

        broadcaster_id = broadcaster_accounts[0]["user_id"]
        broadcaster_name = broadcaster_accounts[0]["username"]

        canal_user = twitchio.PartialUser(
            id=broadcaster_id,
            name=broadcaster_name,
            http=bot._http,
        )

        # 2. Enviar el mensaje usando el token del sender_id correspondiente
        await canal_user.send_message(
            message=message,
            sender=sender_id,
            token_for=sender_id,
        )
        return _ok({"message": "Mensaje enviado con éxito"})
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al enviar el mensaje de chat en Twitch: %s", e)
        return _err(f"Error de Twitch (HTTP {e.status}).", status=502)
    except Exception as e:
        LOGGER.exception("Error inesperado al enviar mensaje de chat: %s", e)
        return _err("Error interno del servidor al enviar el mensaje.", status=500)


async def endpoint_get_ffz_emotes(request: Request) -> Response:
    """Proxy para emotes de FFZ que responde 200 {} si la sala no existe."""
    channel_id = request.path_params.get("channel_id", "").strip()
    if not channel_id or not channel_id.isdigit():
        return _err("channel_id inválido", status=400)

    if channel_id in _FFZ_CACHE:
        return JSONResponse(_FFZ_CACHE[channel_id])

    url = f"https://api.frankerfacez.com/v1/room/id/{channel_id}"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url)
            if len(_FFZ_CACHE) >= MAX_FFZ_CACHE_SIZE:
                _FFZ_CACHE.clear()
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    _FFZ_CACHE[channel_id] = data
                    return JSONResponse(data)
            if resp.status_code == 404:
                _FFZ_CACHE[channel_id] = {}
                return JSONResponse({})
    except Exception as e:
        LOGGER.debug("FFZ channel %s no encontrado o fallo conexión: %s", channel_id, e)

    return JSONResponse({})
