"""REST API: endpoints para ejecutar acciones del bot desde la web."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import twitchio
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bot_tv.actions import (
    action_create_clip,
    action_exit,
    action_get_models,
    action_get_rpm_status,
    action_set_nickname,
    action_switch_model,
    action_sync_followers,
    action_talk,
    action_toggle_bot,
)
from bot_tv.events import AgentResponseEvent

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def _ok(data: object = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


async def _parse_body(request: Request) -> dict:
    """Parsea el body JSON de la request. Retorna dict vacío si no hay body."""
    with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
        body = await request.body()
        if body:
            return json.loads(body)  # type: ignore[return-value]
    return {}


# ── Endpoints ────────────────────────────────────────────────────────────────


async def endpoint_sync_followers(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    results = await action_sync_followers(bot)
    return _ok([{"channel": r.channel, "ok": r.ok, "error": r.error} for r in results])


async def endpoint_toggle_bot(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    if not username:
        return _err("Campo 'username' requerido.")

    result = await action_toggle_bot(bot, username)
    if isinstance(result, str):
        return _err(result)

    return _ok({"username": result.username, "is_bot": result.is_bot})


async def endpoint_set_nickname(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    if not username:
        return _err("Campo 'username' requerido.")

    nickname = body.get("nickname") or None  # string vacío → None (eliminar apodo)

    result = await action_set_nickname(bot, username, nickname)
    if isinstance(result, str):
        return _err(result)

    return _ok({"username": result.username, "nickname": result.nickname})


async def endpoint_switch_model(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    body = await _parse_body(request)
    model = body.get("model", "").strip()
    if not model:
        return _err("Campo 'model' requerido.")

    message = action_switch_model(agent, model)
    return _ok({"message": message, "current_model": agent.current_model})


async def endpoint_talk(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    bot: Bot = request.app.state.bot
    event_bus = bot.event_bus

    body = await _parse_body(request)
    message = body.get("message", "").strip()
    if not message:
        return _err("Campo 'message' requerido.")

    result = await action_talk(agent, message)

    await event_bus.emit(
        AgentResponseEvent(
            timestamp=datetime.now().isoformat(),
            question=message,
            response=result.response,
            model=result.model,
        )
    )

    return _ok({"response": result.response, "model": result.model})


async def endpoint_get_rpm(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    show_all = request.query_params.get("all", "").lower() in ("1", "true", "yes")
    statuses = action_get_rpm_status(agent, show_all)
    return _ok(
        [
            {
                "model": s.model,
                "display_name": s.display_name,
                "rpm_used": s.rpm_used,
                "rpm_limit": s.rpm_limit,
                "rpd_used": s.rpd_used,
                "rpd_limit": s.rpd_limit,
                "is_blocked": s.is_blocked,
                "blocked_reason": s.blocked_reason,
                "next_slot_in": s.next_slot_in,
            }
            for s in statuses
        ]
    )


async def endpoint_get_models(request: Request) -> Response:
    infos = action_get_models()
    return _ok(
        [
            {
                "name": m.name,
                "display_name": m.display_name,
                "enabled": m.enabled,
                "rpm_limit": m.rpm_limit,
                "rpd_limit": m.rpd_limit,
            }
            for m in infos
        ]
    )


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


async def endpoint_search_users(request: Request) -> Response:
    """Busca usuarios en la DB local para autocompletar campos de usuario."""
    bot: Bot = request.app.state.bot
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return _ok([])

    rows = await bot.user_repo.search_users(q, limit=10)

    return _ok(
        [
            {
                "username": r["username"],
                "display_name": r["display_name"],
                "nickname": r["nickname"] or None,
                "is_bot": bool(r["is_bot"]),
                "is_moderator": bool(r["is_moderator"]),
                "is_vip": bool(r["is_vip"]),
                "is_subscriber": bool(r["is_subscriber"]),
                "is_follower": bool(r["is_follower"]),
                "is_broadcaster": str(r["user_id"]) == str(bot.owner_id),
            }
            for r in rows
        ]
    )


async def endpoint_get_chat_accounts(request: Request) -> Response:
    """Retorna las cuentas autenticadas (Bot o Broadcaster) para usar en el chat."""
    bot: Bot = request.app.state.bot
    try:
        tokens_metadata = await bot.token_repo.get_all_tokens_metadata()
        accounts = []
        for row in tokens_metadata:
            user_id = row["user_id"]
            username = row["username"]
            role_type = "bot" if user_id == bot.bot_id else "broadcaster"
            accounts.append({
                "user_id": user_id,
                "username": username,
                "type": role_type
            })
        return _ok(accounts)
    except Exception as e:
        LOGGER.exception("Error al obtener las cuentas de chat: %s", e)
        return _err(f"No se pudieron obtener las cuentas: {e}")


async def endpoint_send_chat_message(request: Request) -> Response:
    """Envía un mensaje de chat desde la cuenta especificada (Bot o Broadcaster)."""
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    sender_id = body.get("sender_id", "").strip()
    message = body.get("message", "").strip()

    if not sender_id:
        return _err("Campo 'sender_id' requerido.")
    if not message:
        return _err("Campo 'message' requerido.")

    try:
        # 1. Obtener la información del canal destino (broadcaster)
        # El canal es aquel cuyo user_id != bot_id en tokens
        async with bot.token_database.acquire() as connection:
            row = await connection.fetchone(
                "SELECT user_id, username FROM tokens WHERE user_id != ?",
                (bot.bot_id,),
            )

        if not row:
            return _err("No se encontró el canal (broadcaster) de destino.")

        broadcaster_id = row["user_id"]
        broadcaster_name = row["username"]

        canal_user = twitchio.PartialUser(
            id=broadcaster_id,
            name=broadcaster_name,
            http=bot._http,
        )

        # 2. Enviar el mensaje usando el token del sender_id correspondiente
        # Si sender_id es el del bot, usa el token del bot.
        # Si es el del broadcaster, usa el del broadcaster.
        await canal_user.send_message(
            message=message,
            sender=sender_id,
            token_for=sender_id,
        )
        return _ok({"message": "Mensaje enviado con éxito"})
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al enviar el mensaje de chat en Twitch: %s", e)
        return _err(f"Error de Twitch (HTTP {e.status}): {e}")
    except Exception as e:
        LOGGER.exception("Error inesperado al enviar mensaje de chat: %s", e)
        return _err(f"Error inesperado: {e}")

