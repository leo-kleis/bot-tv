"""Helpers compartidos para las acciones del bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

import twitchio

if TYPE_CHECKING:
    from bot_tv.bot import Bot


def extract_twitch_error_message(exc: twitchio.HTTPException) -> str:
    """Extrae el mensaje legible de una excepción HTTPException de TwitchIO."""
    if isinstance(exc.extra, dict):
        msg = exc.extra.get("message")
        if msg:
            return str(msg)
    elif isinstance(exc.extra, str) and exc.extra:
        return exc.extra
    return str(exc)


def format_role_http_error(
    action_label: str,
    permission_label: str,
    exc: twitchio.HTTPException,
    *,
    conflict_hint: tuple[str, str] | None = None,
) -> str:
    """Mapea un HTTPException de gestión de roles a un mensaje legible."""
    if exc.status in (401, 403):
        return (
            "Error de permisos en Twitch. Asegúrate de tener los tokens "
            f"del Broadcaster autorizados con los permisos de {permission_label}."
        )
    msg_twitch = extract_twitch_error_message(exc)
    if conflict_hint is not None:
        needle, friendly_msg = conflict_hint
        if needle in msg_twitch.lower():
            return friendly_msg
    return f"Error de Twitch al {action_label}: {msg_twitch}"


async def get_broadcaster_partial(
    bot: Bot,
    channel_id: str | None = None,
    *,
    empty_error: str = "No hay canales configurados.",
) -> twitchio.PartialUser | str:
    """Construye un PartialUser del broadcaster o retorna mensaje de error."""
    channels = await bot.get_channels()
    if not channels:
        return empty_error

    target_id = channel_id or channels[0]["user_id"]
    target_name = next(
        (c["username"] for c in channels if c["user_id"] == target_id),
        channels[0]["username"],
    )
    return twitchio.PartialUser(
        id=target_id,
        name=target_name,
        http=bot.twitch_http,
    )


async def resolve_display_name(bot: Bot, user_id: str, fallback_username: str) -> str:
    """Obtiene el display_name desde caché lista o DB, con fallback al username."""
    cache = bot.ready_user_cache
    if cache is not None:
        cached_user = cache.get_user(user_id)
        if cached_user and cached_user.get("display_name"):
            return str(cached_user["display_name"])
    else:
        info = await bot.user_repo.get_users_info([user_id])
        db_name = info.get(user_id, {}).get("display_name")
        if db_name:
            return db_name
    return fallback_username
