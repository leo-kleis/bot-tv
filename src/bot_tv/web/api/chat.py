"""Endpoints de la API REST relativos al chat y emotes de Twitch."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

import httpx
import twitchio
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bot_tv.utils.network import get_http_client
from bot_tv.web.api.helpers import _err, _get_str, _ok, _parse_body

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

MAX_FFZ_CACHE_SIZE = 32
FFZ_CACHE_TTL_SECONDS = 1800.0
FFZ_EMPTY_CACHE_TTL_SECONDS = 300.0
FFZ_REQUEST_TIMEOUT_SECONDS = 4.0
MAX_CHAT_MESSAGE_LENGTH = 500
_FFZ_CACHE: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()


def _get_ffz_cached(channel_id: str) -> dict[str, Any] | None:
    """Obtiene emotes FFZ cacheados si siguen vigentes y actualiza orden LRU."""
    entry = _FFZ_CACHE.get(channel_id)
    if entry is None:
        return None
    expires_at, data = entry
    if time.monotonic() >= expires_at:
        del _FFZ_CACHE[channel_id]
        return None
    _FFZ_CACHE.move_to_end(channel_id)
    return data


def _set_ffz_cached(channel_id: str, data: dict[str, Any], ttl_seconds: float) -> None:
    """Guarda entrada en caché LRU con TTL monótono y expulsa expiradas/antiguas."""
    now = time.monotonic()
    expired_keys = [k for k, (exp, _) in _FFZ_CACHE.items() if now >= exp]
    for key in expired_keys:
        del _FFZ_CACHE[key]

    if channel_id in _FFZ_CACHE:
        _FFZ_CACHE.move_to_end(channel_id)
    _FFZ_CACHE[channel_id] = (now + ttl_seconds, data)

    while len(_FFZ_CACHE) > MAX_FFZ_CACHE_SIZE:
        _FFZ_CACHE.popitem(last=False)


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
    if len(message) > MAX_CHAT_MESSAGE_LENGTH:
        return _err(
            f"El mensaje supera el límite de {MAX_CHAT_MESSAGE_LENGTH} "
            "caracteres de Twitch."
        )

    try:
        # 1. Obtener la información de cuentas autenticadas y validar sender_id
        tokens_metadata = await bot.token_repo.get_accounts_summary()
        authorized_sender_ids = {t["user_id"] for t in tokens_metadata}
        if sender_id not in authorized_sender_ids:
            return _err(
                "El 'sender_id' especificado no corresponde a una cuenta autorizada.",
                status=403,
            )

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
            http=bot.twitch_http,
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

    cached = _get_ffz_cached(channel_id)
    if cached is not None:
        return JSONResponse(cached)

    url = f"https://api.frankerfacez.com/v1/room/id/{channel_id}"
    try:
        client = get_http_client()
        resp = await client.get(url, timeout=FFZ_REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                _set_ffz_cached(channel_id, data, FFZ_CACHE_TTL_SECONDS)
                return JSONResponse(data)
        if resp.status_code == 404:
            _set_ffz_cached(channel_id, {}, FFZ_EMPTY_CACHE_TTL_SECONDS)
            return JSONResponse({})
    except (httpx.HTTPError, TimeoutError, ValueError, RuntimeError) as e:
        LOGGER.debug("FFZ channel %s no encontrado o fallo conexión: %s", channel_id, e)

    return JSONResponse({})
