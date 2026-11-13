"""Endpoints de la API REST relativos a la gestión de usuarios y seguidores."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from bot_tv.actions.followers import action_sync_followers
from bot_tv.actions.moderation import action_get_user_ban_status
from bot_tv.actions.users import (
    action_set_nickname,
    action_sync_user_roles,
    action_update_user_roles,
)
from bot_tv.web.api.helpers import (
    _err,
    _get_str,
    _ok,
    _parse_body,
    _parse_int_param,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

MAX_USERS_PAGE_LIMIT = 200
MAX_USER_MESSAGES_LIMIT = 100
DEFAULT_USERS_PAGE_LIMIT = 50
DEFAULT_USER_MESSAGES_LIMIT = 50
ALLOWED_AVATAR_HOST = "static-cdn.jtvnw.net"


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
    username = _get_str(body, "username")
    if not username:
        return _err("Campo 'username' requerido.")

    # string vacío → None (eliminar apodo)
    nickname = _get_str(body, "nickname") or None

    result = await action_set_nickname(bot, username, nickname)
    if isinstance(result, str):
        return _err(result)

    return _ok({"username": result.username, "nickname": result.nickname})


async def endpoint_update_user_roles(request: Request) -> Response:
    bot: Bot = request.app.state.bot
    body = await _parse_body(request)
    username = _get_str(body, "username")
    if not username:
        return _err("Campo 'username' requerido.")

    is_bot = bool(body.get("is_bot", False))
    is_moderator = bool(body.get("is_moderator", False))
    is_vip = bool(body.get("is_vip", False))

    channels = await bot.get_channels()
    channel_id = _get_str(body, "channel_id") or (
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
    username = _get_str(body, "username")
    if not username:
        return _err("Campo 'username' requerido.")

    channels = await bot.get_channels()
    channel_id = _get_str(body, "channel_id") or (
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


async def endpoint_search_users(request: Request) -> Response:
    """Busca usuarios en la caché/DB local para autocompletar campos de usuario."""
    bot: Bot = request.app.state.bot
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return _ok([])

    channels = await bot.get_channels()
    channel_id = channels[0]["user_id"] if channels else None
    rows = await bot.user_repo.search_users(
        q, limit=10, channel_id=channel_id, cache=bot.ready_user_cache
    )

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


async def endpoint_list_users(request: Request) -> Response:
    """Retorna un listado de todos los usuarios registrados con filtros avanzados."""
    bot: Bot = request.app.state.bot
    channels = await bot.get_channels()
    if not channels:
        return _err("No hay canales configurados.")

    channel_id = request.query_params.get("channel_id", channels[0]["user_id"])

    name = request.query_params.get("name", "").strip() or None
    role = request.query_params.get("role", "").strip() or None

    has_history_param = request.query_params.get("has_history", "").strip().lower()
    has_chat_history: bool | None = None
    if has_history_param in ("true", "1", "with_history"):
        has_chat_history = True
    elif has_history_param in ("false", "0", "no_history"):
        has_chat_history = False

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

    limit = _parse_int_param(
        request,
        "limit",
        DEFAULT_USERS_PAGE_LIMIT,
        min_val=1,
        max_val=MAX_USERS_PAGE_LIMIT,
    )
    if isinstance(limit, JSONResponse):
        return limit

    page = _parse_int_param(request, "page", 1, min_val=1, max_val=None)
    if isinstance(page, JSONResponse):
        return page

    offset = (page - 1) * limit

    try:
        rows, total_count = await bot.user_repo.list_users_with_filters(
            channel_id=channel_id,
            broadcaster_id=channel_id,
            role=role,
            has_chat_history=has_chat_history,
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
            cache=bot.ready_user_cache,
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
                "message_count": r.get("message_count", 0),
            }
            for r in rows
        ]

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
        return _err("Error interno del servidor al listar usuarios.", status=500)


async def endpoint_get_avatar(request: Request) -> Response:
    """Redirige a la URL del avatar de Twitch cacheada en memoria o DB."""
    user_id = request.path_params.get("user_id", "")
    if not user_id:
        return _err("user_id requerido", 400)

    bot: Bot = request.app.state.bot
    url = await bot.user_repo.get_profile_image_url(user_id, cache=bot.ready_user_cache)
    if not url:
        return _err("Avatar no encontrado", 404)

    clean_url = url.strip()
    if any(ch in clean_url for ch in ("\r", "\n", "\x00")):
        LOGGER.warning(
            "Avatar con caracteres inválidos bloqueado para user_id %s", user_id
        )
        return _err("URL de avatar inválida", 400)

    try:
        parsed = urlsplit(clean_url)
    except ValueError:
        LOGGER.warning("Avatar con URL malformada bloqueado para user_id %s", user_id)
        return _err("URL de avatar inválida", 400)

    if (
        parsed.scheme != "https"
        or parsed.hostname != ALLOWED_AVATAR_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        LOGGER.warning(
            "Redirección de avatar bloqueada para user_id %s (host=%s, scheme=%s)",
            user_id,
            parsed.hostname,
            parsed.scheme,
        )
        return _err("URL de avatar inválida", 400)

    return RedirectResponse(url=clean_url, status_code=302)


async def endpoint_get_user_detail(request: Request) -> Response:
    """Retorna los datos consolidados de un usuario para el drawer de perfil."""
    bot: Bot = request.app.state.bot
    username = request.path_params.get("username", "").strip()
    if not username:
        return _err("username requerido")

    channels = await bot.get_channels()
    if not channels:
        return _err("No hay canales configurados.")
    channel_id = channels[0]["user_id"]

    row = await bot.user_repo.get_user_detail_by_name(
        username, channel_id, cache=bot.ready_user_cache
    )
    if not row:
        return _err(f"Usuario '{username}' no encontrado.", status=404)

    is_follower = (
        row.get("followed_at") is not None and row.get("unfollowed_at") is None
    )
    user_id = str(row.get("user_id") or "")
    if not user_id:
        user_id = (
            await bot.user_repo.get_user_id_by_name(
                username, cache=bot.ready_user_cache
            )
            or ""
        )
    is_broadcaster = user_id == str(bot.owner_id) or user_id == channel_id

    ban_status = await action_get_user_ban_status(bot, username)

    return _ok(
        {
            "user_id": user_id,
            "username": row["username"],
            "display_name": row["display_name"],
            "nickname": row["nickname"],
            "is_bot": bool(row["is_bot"]),
            "is_moderator": bool(row["is_moderator"]),
            "is_vip": bool(row["is_vip"]),
            "is_subscriber": bool(row["is_subscriber"]),
            "followed_at": row.get("followed_at"),
            "unfollowed_at": row.get("unfollowed_at"),
            "is_follower": is_follower,
            "is_broadcaster": is_broadcaster,
            "is_banned": ban_status.is_banned,
            "ban_permanent": ban_status.permanent,
            "ban_expires_at": ban_status.expires_at,
            "ban_reason": ban_status.reason,
        }
    )


async def endpoint_user_messages(request: Request) -> Response:
    """Retorna el historial de mensajes de un usuario con paginación."""
    bot: Bot = request.app.state.bot
    username = request.path_params.get("username", "").strip()
    if not username:
        return _err("username requerido")

    channels = await bot.get_channels()
    if not channels:
        return _err("No hay canales configurados.")
    channel_id = channels[0]["user_id"]

    limit = _parse_int_param(
        request,
        "limit",
        DEFAULT_USER_MESSAGES_LIMIT,
        min_val=1,
        max_val=MAX_USER_MESSAGES_LIMIT,
    )
    if isinstance(limit, JSONResponse):
        return limit

    offset = _parse_int_param(request, "offset", 0, min_val=0, max_val=None)
    if isinstance(offset, JSONResponse):
        return offset

    search = request.query_params.get("search", "").strip() or None
    since = request.query_params.get("since", "").strip() or None
    until = request.query_params.get("until", "").strip() or None

    if since and len(since) == 10:
        since = f"{since}T00:00:00Z"
    if until and len(until) == 10:
        until = f"{until}T23:59:59Z"

    try:
        user_id = (
            await bot.user_repo.get_user_id_by_name(
                username, cache=bot.ready_user_cache
            )
            or ""
        )
        messages = await bot.chat_repo.get_messages_with_filters(
            channel_id=channel_id,
            username=username,
            search_term=search,
            since=since,
            until=until,
            limit=limit + 1,  # pedir uno extra para detectar has_more
            offset=offset,
        )
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        total = await bot.chat_repo.get_user_message_count(
            channel_id,
            user_id,
            search_term=search,
            since=since,
            until=until,
        )

        return _ok(
            {
                "messages": messages,
                "total": total,
                "has_more": has_more,
                "offset": offset,
                "limit": limit,
            }
        )
    except Exception as e:
        LOGGER.exception("Error al obtener mensajes del usuario %s: %s", username, e)
        return _err("Error interno del servidor al obtener mensajes.", status=500)
