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
from starlette.responses import JSONResponse, RedirectResponse, Response

from bot_tv.actions import (
    action_clear_agent_chat,
    action_create_clip,
    action_exit,
    action_get_models,
    action_get_rpm_status,
    action_set_context_limit,
    action_set_nickname,
    action_switch_model,
    action_sync_followers,
    action_sync_user_roles,
    action_talk,
    action_update_user_roles,
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
    errors = [r.error for r in results if not r.ok and r.error]
    if errors:
        return _err(errors[0], status=409)
    return _ok([{"channel": r.channel, "ok": r.ok, "error": r.error} for r in results])


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


async def endpoint_update_user_roles(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    if not username:
        return _err("Campo 'username' requerido.")

    is_bot = bool(body.get("is_bot", False))
    is_moderator = bool(body.get("is_moderator", False))
    is_vip = bool(body.get("is_vip", False))

    channels = await bot.get_channels()
    channel_id = body.get("channel_id") or (
        channels[0]["user_id"] if channels else None
    )

    result = await action_update_user_roles(
        bot,
        username,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        channel_id=channel_id,
    )
    if isinstance(result, str):
        return _err(result)

    return _ok(
        {
            "username": result.username,
            "is_bot": result.is_bot,
            "is_moderator": result.is_moderator,
            "is_vip": result.is_vip,
            "is_subscriber": result.is_subscriber,
        }
    )


async def endpoint_sync_user_roles(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = body.get("username", "").strip()
    if not username:
        return _err("Campo 'username' requerido.")

    channels = await bot.get_channels()
    channel_id = body.get("channel_id") or (
        channels[0]["user_id"] if channels else None
    )

    result = await action_sync_user_roles(bot, username, channel_id=channel_id)
    if isinstance(result, str):
        return _err(result)

    return _ok(
        {
            "username": result.username,
            "is_bot": result.is_bot,
            "is_moderator": result.is_moderator,
            "is_vip": result.is_vip,
            "is_subscriber": result.is_subscriber,
        }
    )


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


async def endpoint_clear_agent_chat(request: Request) -> Response:
    """Limpia la memoria conversacional del agente."""
    agent: TalkAgent = request.app.state.agent
    action_clear_agent_chat(agent)
    return _ok({"message": "Historial de conversación limpiado."})


async def endpoint_set_context_limit(request: Request) -> Response:
    """Actualiza y persiste el límite de contexto del agente."""
    agent: TalkAgent = request.app.state.agent
    body = await _parse_body(request)
    limit_val = body.get("limit", 0)
    try:
        limit = max(0, int(limit_val))
    except ValueError, TypeError:
        return _err("El campo 'limit' debe ser un número entero >= 0.")

    await action_set_context_limit(agent, limit)
    return _ok(
        {
            "message": f"Límite de contexto actualizado a {limit}.",
            "context_limit": agent.context_limit,
        }
    )


async def endpoint_get_rpm(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    show_all = request.query_params.get("all", "").lower() in ("1", "true", "yes")
    statuses = action_get_rpm_status(agent, show_all)
    return _ok(
        {
            "context_limit": agent.context_limit,
            "statuses": [
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
            ],
        }
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
            accounts.append(
                {"user_id": user_id, "username": username, "type": role_type}
            )
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
        async with bot.database.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT user_id, username FROM tokens WHERE user_id != $1",
                bot.bot_id,
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


async def endpoint_list_users(request: Request) -> Response:
    """Retorna un listado de todos los usuarios registrados con filtros avanzados."""
    bot: Bot = request.app.state.bot
    channels = await bot.get_channels()
    if not channels:
        return _err("No hay canales configurados.")

    channel_id = request.query_params.get("channel_id", channels[0]["user_id"])

    name = request.query_params.get("name", "").strip() or None
    role = request.query_params.get("role", "").strip() or None

    is_follower_param = request.query_params.get("is_follower", "").lower()
    is_follower: str | None = None
    if is_follower_param in ("follower", "not_follower", "unfollower"):
        is_follower = is_follower_param

    followed_after = request.query_params.get("followed_after", "").strip() or None
    followed_before = request.query_params.get("followed_before", "").strip() or None
    unfollowed_after = request.query_params.get("unfollowed_after", "").strip() or None
    unfollowed_before = (
        request.query_params.get("unfollowed_before", "").strip() or None
    )

    # Formatear fechas YYYY-MM-DD a ISO 8601 completo
    if followed_after and len(followed_after) == 10:
        followed_after = f"{followed_after}T00:00:00Z"
    if followed_before and len(followed_before) == 10:
        followed_before = f"{followed_before}T23:59:59Z"
    if unfollowed_after and len(unfollowed_after) == 10:
        unfollowed_after = f"{unfollowed_after}T00:00:00Z"
    if unfollowed_before and len(unfollowed_before) == 10:
        unfollowed_before = f"{unfollowed_before}T23:59:59Z"

    sort_by = request.query_params.get("sort_by", "username").strip().lower()
    if sort_by not in ("username", "role", "follow_date"):
        sort_by = "username"

    sort_order = request.query_params.get("sort_order", "asc").strip().lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    limit_param = request.query_params.get("limit", "50")
    try:
        limit = int(limit_param)
    except ValueError:
        limit = 50

    page_param = request.query_params.get("page", "1")
    try:
        page = int(page_param)
    except ValueError:
        page = 1

    offset = (page - 1) * limit

    try:
        rows, total_count = await bot.user_repo.list_users_with_filters(
            channel_id=channel_id,
            broadcaster_id=bot.owner_id,
            role=role,
            username_search=name,
            followed_after=followed_after,
            followed_before=followed_before,
            unfollowed_after=unfollowed_after,
            unfollowed_before=unfollowed_before,
            is_follower=is_follower,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            cache=bot.user_cache,
        )

        users_list = [
            {
                "user_id": r.get("user_id"),
                "username": r["username"],
                "display_name": r["display_name"],
                "nickname": r["nickname"] or None,
                "is_bot": bool(r["is_bot"]),
                "is_moderator": bool(r["is_moderator"]),
                "is_vip": bool(r["is_vip"]),
                "is_subscriber": bool(r["is_subscriber"]),
                "sub_tier": r.get("sub_tier"),
                "followed_at": r.get("followed_at"),
                "unfollowed_at": r.get("unfollowed_at"),
                "is_follower": r.get("followed_at") is not None
                and r.get("unfollowed_at") is None,
                "is_broadcaster": r.get("user_id") == channel_id,
            }
            for r in rows
        ]

        if is_follower is not None:
            users_list = [u for u in users_list if not u["is_broadcaster"]]

        return _ok(
            {
                "users": users_list,
                "total": total_count,
                "page": page,
                "limit": limit,
            }
        )
    except Exception as e:
        LOGGER.exception("Error inesperado al listar usuarios: %s", e)
        return _err(f"Error al listar usuarios: {e}")


async def endpoint_get_avatar(request: Request) -> Response:
    """Redirige a la URL del avatar de Twitch cacheada en la DB."""
    user_id = request.path_params.get("user_id", "")
    if not user_id:
        return _err("user_id requerido", 400)

    bot: Bot = request.app.state.bot
    url = await bot.user_repo.get_profile_image_url(user_id)
    if not url:
        return _err("Avatar no encontrado", 404)

    return RedirectResponse(url=url, status_code=302)
