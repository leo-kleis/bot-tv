"""Acciones de gestión de usuarios y roles del bot."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import twitchio

from bot_tv.actions.models import (
    BotToggleResult,
    NicknameResult,
    UserResolveResult,
    UserRolesResult,
)
from bot_tv.events import (
    UserNicknameUpdatedEvent,
    UserRoleUpdatedEvent,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def _sync_irc_user(
    bot: Bot,
    user_id: str,
    username: str,
    *,
    nickname: str | None = None,
    update_nickname: bool = False,
    is_bot: bool | None = None,
    is_moderator: bool | None = None,
    is_vip: bool | None = None,
    is_subscriber: bool | None = None,
    sub_tier: str | None = None,
    update_sub_tier: bool = False,
) -> None:
    """Actualiza en memoria y emite el UserJoinEvent de un usuario conectado en IRC."""
    if not bot.irc:
        return

    key = (
        user_id
        if user_id in bot.irc.connected_users
        else (username.lower() if username.lower() in bot.irc.connected_users else None)
    )
    if not key:
        u_lower = username.lower()
        for k, v in bot.irc.connected_users.items():
            if (user_id and v.user_id == user_id) or v.username.lower() == u_lower:
                key = k
                break

    if key:
        from dataclasses import replace as dataclass_replace

        u = bot.irc.connected_users[key]
        updated_u = dataclass_replace(
            u,
            nickname=nickname if update_nickname else u.nickname,
            is_bot=is_bot if is_bot is not None else u.is_bot,
            is_moderator=is_moderator if is_moderator is not None else u.is_moderator,
            is_vip=is_vip if is_vip is not None else u.is_vip,
            is_subscriber=(
                is_subscriber if is_subscriber is not None else u.is_subscriber
            ),
            sub_tier=sub_tier if update_sub_tier else u.sub_tier,
        )
        target_key = user_id or key
        if target_key != key:
            bot.irc.connected_users.pop(key, None)
        bot.irc.connected_users[target_key] = updated_u
        await bot.event_bus.emit(updated_u)


async def resolve_user(bot: Bot, username: str) -> UserResolveResult:
    """Busca user_id en DB local; si no está, consulta la API de Twitch."""
    user_id = await bot.user_repo.get_user_id_by_name(username)
    if user_id:
        return UserResolveResult(
            user_id=user_id, found_locally=True, found_on_twitch=False
        )

    try:
        twitch_user = await bot.fetch_user(login=username)
        if not twitch_user:
            return UserResolveResult(
                user_id=None,
                found_locally=False,
                found_on_twitch=False,
                error=f"Usuario '{username}' no encontrado en Twitch.",
            )

        user_id = twitch_user.id
        await bot.user_repo.upsert_user(
            user_id,
            twitch_user.name or username,
            twitch_user.display_name,
        )
        return UserResolveResult(
            user_id=user_id, found_locally=False, found_on_twitch=True
        )
    except Exception as e:
        LOGGER.exception("Error al buscar usuario en Twitch.")
        return UserResolveResult(
            user_id=None,
            found_locally=False,
            found_on_twitch=False,
            error=str(e),
        )


async def action_toggle_bot(bot: Bot, username: str) -> BotToggleResult | str:
    """Marca/desmarca un usuario como bot. Retorna BotToggleResult o string de error."""
    cache = bot.user_cache
    user_id = await bot.user_repo.get_user_id_by_name(username.lower(), cache=cache)
    if not user_id:
        return f"El usuario '{username}' no existe en la base de datos."

    es_bot = await bot.user_repo.is_user_bot(user_id, cache=cache)
    nuevo_es_bot = not es_bot
    await bot.user_repo.set_user_bot(user_id, nuevo_es_bot, cache=cache)

    await _sync_irc_user(bot, user_id, username, is_bot=nuevo_es_bot)

    display_name = username
    if cache is not None:
        cached_user = cache.get_user(user_id)
        if cached_user and cached_user.get("display_name"):
            display_name = cached_user["display_name"]

    channels = await bot.get_channels()
    broadcaster_id = channels[0]["user_id"] if channels else ""
    roles_dict = await bot.user_repo.get_user_roles(
        user_id, broadcaster_id, cache=cache
    )
    current_roles = roles_dict or {}

    await bot.event_bus.emit(
        UserRoleUpdatedEvent(
            user_id=user_id,
            username=username,
            display_name=display_name,
            is_bot=nuevo_es_bot,
            is_moderator=current_roles.get("is_moderator", False),
            is_vip=current_roles.get("is_vip", False),
            is_subscriber=current_roles.get("is_subscriber", False),
        )
    )

    return BotToggleResult(
        username=username,
        is_bot=nuevo_es_bot,
        user_id=user_id,
    )


async def action_set_nickname(
    bot: Bot, username: str, nickname: str | None
) -> NicknameResult | str:
    """Asigna o elimina el apodo de un usuario."""
    cache = bot.user_cache
    user_id = await bot.user_repo.get_user_id_by_name(username.lower(), cache=cache)
    if not user_id:
        return f"El usuario '{username}' no existe en la base de datos."

    await bot.user_repo.set_nickname(user_id, nickname, cache=cache)

    await _sync_irc_user(
        bot, user_id, username, nickname=nickname, update_nickname=True
    )

    display_name = username
    if cache is not None:
        cached_user = cache.get_user(user_id)
        if cached_user and cached_user.get("display_name"):
            display_name = cached_user["display_name"]

    await bot.event_bus.emit(
        UserNicknameUpdatedEvent(
            user_id=user_id,
            username=username,
            display_name=display_name,
            nickname=nickname,
        )
    )

    return NicknameResult(username=username, nickname=nickname)


async def action_update_user_roles(
    bot: Bot,
    username: str,
    is_bot: bool,
    is_moderator: bool,
    is_vip: bool,
    channel_id: str | None = None,
) -> UserRolesResult | str:
    """Actualiza los roles de un usuario en Twitch y en la DB."""
    cache = bot.user_cache
    user_id = await bot.user_repo.get_user_id_by_name(username.lower(), cache=cache)
    if not user_id:
        try:
            twitch_user = await bot.fetch_user(login=username)
            if not twitch_user:
                return (
                    f"El usuario '{username}' no existe en Twitch "
                    "ni en la base de datos."
                )
            user_id = twitch_user.id
            await bot.user_repo.upsert_user(
                user_id,
                twitch_user.name or username,
                twitch_user.display_name,
                cache=cache,
            )
        except Exception as e:
            LOGGER.exception("Error al buscar usuario en Twitch: %s", e)
            return f"Error al buscar al usuario '{username}' en Twitch: {e}"

    channels = await bot.get_channels()
    if not channels:
        return "No hay canales configurados."
    broadcaster_id = channel_id or channels[0]["user_id"]

    if user_id == broadcaster_id:
        return "No se pueden modificar los roles del broadcaster."

    current_roles = await bot.user_repo.get_user_roles(
        user_id, broadcaster_id, cache=cache
    )
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False
    current_sub = current_roles.get("is_subscriber", False) if current_roles else False

    broadcaster = twitchio.PartialUser(id=broadcaster_id, http=bot._http)

    if not is_moderator and current_mod:
        try:
            await broadcaster.remove_moderator(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al quitar moderador para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de moderación."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            return f"Error de Twitch al quitar moderación: {msg_twitch}"

    if not is_vip and current_vip:
        try:
            await broadcaster.remove_vip(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al quitar VIP para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de VIP."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            return f"Error de Twitch al quitar VIP: {msg_twitch}"

    if is_moderator and not current_mod:
        try:
            await broadcaster.add_moderator(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error(
                "Error al agregar moderador para %s en Twitch: %s", username, e
            )
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de moderación."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            if msg_twitch and "vip of this channel" in msg_twitch.lower():
                return (
                    "El usuario ya es VIP del canal y no puede ser moderador "
                    "al mismo tiempo."
                )
            return f"Error de Twitch al agregar moderador: {msg_twitch}"

    if is_vip and not current_vip:
        try:
            await broadcaster.add_vip(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al agregar VIP para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de VIP."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            if msg_twitch and "moderator of this channel" in msg_twitch.lower():
                return (
                    "El usuario ya es moderador del canal y no puede ser VIP "
                    "al mismo tiempo."
                )
            return f"Error de Twitch al agregar VIP: {msg_twitch}"

    await bot.user_repo.update_user_roles(
        user_id=user_id,
        channel_id=broadcaster_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        cache=cache,
    )

    await _sync_irc_user(
        bot,
        user_id,
        username,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_bot=is_bot,
    )

    display_name = username
    if cache is not None:
        cached_user = cache.get_user(user_id)
        if cached_user and cached_user.get("display_name"):
            display_name = cached_user["display_name"]

    await bot.event_bus.emit(
        UserRoleUpdatedEvent(
            user_id=user_id,
            username=username,
            display_name=display_name,
            is_bot=is_bot,
            is_moderator=is_moderator,
            is_vip=is_vip,
            is_subscriber=current_sub,
        )
    )

    return UserRolesResult(
        username=username,
        user_id=user_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=current_sub,
    )


async def action_sync_user_roles(
    bot: Bot,
    username: str,
    channel_id: str | None = None,
) -> UserRolesResult | str:
    """Consulta Twitch para sincronizar los roles actuales de un usuario."""
    user_id = await bot.user_repo.get_user_id_by_name(username.lower())
    if not user_id:
        try:
            twitch_user = await bot.fetch_user(login=username)
            if not twitch_user:
                return f"El usuario '{username}' no existe en Twitch."
            user_id = twitch_user.id
            await bot.user_repo.upsert_user(
                user_id,
                twitch_user.name or username,
                twitch_user.display_name,
            )
        except Exception as e:
            LOGGER.exception("Error al buscar usuario en Twitch: %s", e)
            return f"Error al buscar al usuario '{username}' en Twitch: {e}"

    channels = await bot.get_channels()
    if not channels:
        return "No hay canales configurados."
    broadcaster_id = channel_id or channels[0]["user_id"]

    if user_id == broadcaster_id:
        await bot.user_repo.update_user_roles(
            user_id=user_id,
            channel_id=broadcaster_id,
            is_bot=False,
            is_moderator=True,
            is_vip=False,
            is_subscriber=False,
            sub_tier=None,
            gifter_id=None,
        )
        return UserRolesResult(
            username=username,
            user_id=user_id,
            is_bot=False,
            is_moderator=True,
            is_vip=False,
            is_subscriber=False,
        )

    current_roles = await bot.user_repo.get_user_roles(user_id, broadcaster_id)
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False
    current_sub = current_roles.get("is_subscriber", False) if current_roles else False

    is_moderator = current_mod
    is_vip = current_vip
    is_subscriber = current_sub

    broadcaster = twitchio.PartialUser(id=broadcaster_id, http=bot._http)

    try:
        moderators = await broadcaster.fetch_moderators()
        is_moderator = any(m.id == user_id for m in moderators)
    except twitchio.HTTPException as e:
        LOGGER.warning(
            "No se pudieron sincronizar moderadores de Twitch para %s (HTTP %s): %s",
            username,
            e.status,
            e,
        )

    try:
        vips = await broadcaster.fetch_vips(user_ids=[user_id])
        is_vip = any(v.id == user_id for v in vips)
    except twitchio.HTTPException as e:
        LOGGER.warning(
            "No se pudieron sincronizar VIPs de Twitch para %s (HTTP %s): %s",
            username,
            e.status,
            e,
        )

    is_subscriber = False
    sub_tier = None
    gifter_id = None
    try:
        data = await bot._http.get_broadcaster_subscriptions(
            token_for=broadcaster_id,
            broadcaster_id=broadcaster_id,
            user_ids=[user_id],
        )
        async for sub in data.subscriptions:
            is_subscriber = True
            sub_tier = sub.tier
            if sub.gift and sub.gifter and sub.gifter.name:
                gifter_id = sub.gifter.id
                gifter_name = sub.gifter.name
                existing = await bot.user_repo.get_user_id_by_name(gifter_name.lower())
                if not existing:
                    try:
                        gifter_user = await bot.fetch_user(id=gifter_id)
                        if gifter_user and gifter_user.name:
                            await bot.user_repo.upsert_user(
                                gifter_user.id,
                                gifter_user.name,
                                gifter_user.display_name,
                            )
                    except Exception as eg:
                        LOGGER.warning(
                            "No se pudo upsert el gifter %s: %s", gifter_id, eg
                        )
            break
    except twitchio.HTTPException as e:
        if e.status == 404:
            is_subscriber = False
        elif e.status in (401, 403):
            is_subscriber = False
            twitch_msg = ""
            if isinstance(e.extra, dict) and "message" in e.extra:
                twitch_msg = f": {e.extra['message']}"
            elif isinstance(e.extra, str):
                twitch_msg = f": {e.extra}"
            LOGGER.warning(
                "No se pudo comprobar la suscripción para %s (HTTP %s)%s",
                username,
                e.status,
                twitch_msg,
            )
        else:
            twitch_msg = ""
            if isinstance(e.extra, dict) and "message" in e.extra:
                twitch_msg = f": {e.extra['message']}"
            elif isinstance(e.extra, str):
                twitch_msg = f": {e.extra}"
            LOGGER.warning(
                "Error al obtener suscripción de Twitch para %s (HTTP %s)%s",
                username,
                e.status,
                twitch_msg,
            )
    except Exception as e:
        LOGGER.warning(
            "Error inesperado al comprobar suscripción para %s: %s",
            username,
            e,
        )

    cache = bot.user_cache
    is_bot = cache.is_user_bot(user_id) if cache is not None else False

    updated = await bot.user_repo.update_user_roles(
        user_id=user_id,
        channel_id=broadcaster_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=is_subscriber,
        sub_tier=sub_tier,
        gifter_id=gifter_id,
        cache=cache,
    )

    if updated:
        await _sync_irc_user(
            bot,
            user_id,
            username,
            is_moderator=is_moderator,
            is_vip=is_vip,
            is_bot=is_bot,
            is_subscriber=is_subscriber,
            sub_tier=sub_tier,
            update_sub_tier=True,
        )

        display_name = username
        if cache is not None:
            cached_user = cache.get_user(user_id)
            if cached_user and cached_user.get("display_name"):
                display_name = cached_user["display_name"]

        await bot.event_bus.emit(
            UserRoleUpdatedEvent(
                user_id=user_id,
                username=username,
                display_name=display_name,
                is_bot=is_bot,
                is_moderator=is_moderator,
                is_vip=is_vip,
                is_subscriber=is_subscriber,
            )
        )

    return UserRolesResult(
        username=username,
        user_id=user_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=is_subscriber,
        sub_tier=sub_tier,
        gifter_id=gifter_id,
    )
