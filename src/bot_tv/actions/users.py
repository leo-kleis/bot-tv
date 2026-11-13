"""Acciones de gestión de usuarios y roles del bot."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import twitchio

from bot_tv.actions._helpers import (
    extract_twitch_error_message,
    format_role_http_error,
    get_broadcaster_partial,
    resolve_display_name,
)
from bot_tv.actions.models import (
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
    role: str | None = None,
    update_role: bool = False,
    is_bot: bool | None = None,
    is_moderator: bool | None = None,
    is_vip: bool | None = None,
    is_subscriber: bool | None = None,
    sub_tier: str | None = None,
    update_sub_tier: bool = False,
) -> None:
    """Delega al cliente IRC la actualización de estado de un usuario conectado."""
    if not bot.irc:
        return
    await bot.irc.sync_user_state(
        user_id,
        username,
        nickname=nickname,
        update_nickname=update_nickname,
        role=role,
        update_role=update_role,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=is_subscriber,
        sub_tier=sub_tier,
        update_sub_tier=update_sub_tier,
    )


async def resolve_user(bot: Bot, username: str) -> UserResolveResult:
    """Busca user_id en caché/DB local; si no está, consulta la API de Twitch."""
    cache = bot.ready_user_cache
    user_id = await bot.user_repo.get_user_id_by_name(username.lower(), cache=cache)
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
            cache=bot.ready_user_cache,
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


async def action_set_nickname(
    bot: Bot, username: str, nickname: str | None
) -> NicknameResult | str:
    """Asigna o elimina el apodo de un usuario."""
    cache = bot.ready_user_cache
    user_id = await bot.user_repo.get_user_id_by_name(username.lower(), cache=cache)
    if not user_id:
        return f"El usuario '{username}' no existe en la base de datos."

    await bot.user_repo.set_nickname(user_id, nickname, cache=bot.ready_user_cache)

    await _sync_irc_user(
        bot, user_id, username, nickname=nickname, update_nickname=True
    )

    display_name = await resolve_display_name(bot, user_id, username)

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
    res = await resolve_user(bot, username)
    if not res.user_id:
        return (
            res.error
            or f"El usuario '{username}' no existe en Twitch ni en la base de datos."
        )
    user_id = res.user_id

    broadcaster = await get_broadcaster_partial(bot, channel_id=channel_id)
    if isinstance(broadcaster, str):
        return broadcaster
    broadcaster_id = broadcaster.id

    if user_id == broadcaster_id:
        return "No se pueden modificar los roles del broadcaster."

    cache = bot.ready_user_cache
    current_roles = await bot.user_repo.get_user_roles(
        user_id, broadcaster_id, cache=cache
    )
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False
    current_sub = current_roles.get("is_subscriber", False) if current_roles else False

    if not is_moderator and current_mod:
        try:
            await broadcaster.remove_moderator(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al quitar moderador para %s en Twitch: %s", username, e)
            return format_role_http_error("quitar moderación", "moderación", e)

    if not is_vip and current_vip:
        try:
            await broadcaster.remove_vip(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al quitar VIP para %s en Twitch: %s", username, e)
            return format_role_http_error("quitar VIP", "VIP", e)

    if is_moderator and not current_mod:
        try:
            await broadcaster.add_moderator(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error(
                "Error al agregar moderador para %s en Twitch: %s", username, e
            )
            return format_role_http_error(
                "agregar moderador",
                "moderación",
                e,
                conflict_hint=(
                    "vip of this channel",
                    "El usuario ya es VIP del canal y no puede ser moderador "
                    "al mismo tiempo.",
                ),
            )

    if is_vip and not current_vip:
        try:
            await broadcaster.add_vip(user=user_id)
        except twitchio.HTTPException as e:
            LOGGER.error("Error al agregar VIP para %s en Twitch: %s", username, e)
            return format_role_http_error(
                "agregar VIP",
                "VIP",
                e,
                conflict_hint=(
                    "moderator of this channel",
                    "El usuario ya es moderador del canal y no puede ser VIP "
                    "al mismo tiempo.",
                ),
            )

    await bot.user_repo.update_user_roles(
        user_id=user_id,
        channel_id=broadcaster_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        cache=bot.ready_user_cache,
    )

    await _sync_irc_user(
        bot,
        user_id,
        username,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_bot=is_bot,
    )

    display_name = await resolve_display_name(bot, user_id, username)

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
    res = await resolve_user(bot, username)
    if not res.user_id:
        return res.error or f"El usuario '{username}' no existe en Twitch."
    user_id = res.user_id

    broadcaster = await get_broadcaster_partial(bot, channel_id=channel_id)
    if isinstance(broadcaster, str):
        return broadcaster
    broadcaster_id = broadcaster.id

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
            cache=bot.ready_user_cache,
        )
        return UserRolesResult(
            username=username,
            user_id=user_id,
            is_bot=False,
            is_moderator=True,
            is_vip=False,
            is_subscriber=False,
        )

    cache = bot.ready_user_cache
    current_roles = await bot.user_repo.get_user_roles(
        user_id, broadcaster_id, cache=cache
    )
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False

    is_moderator = current_mod
    is_vip = current_vip

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
        data = await bot.twitch_http.get_broadcaster_subscriptions(
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
                existing = await bot.user_repo.get_user_id_by_name(
                    gifter_name.lower(), cache=bot.ready_user_cache
                )
                if not existing:
                    try:
                        gifter_user = await bot.fetch_user(id=gifter_id)
                        if gifter_user and gifter_user.name:
                            await bot.user_repo.upsert_user(
                                gifter_user.id,
                                gifter_user.name,
                                gifter_user.display_name,
                                cache=bot.ready_user_cache,
                            )
                    except Exception as eg:
                        LOGGER.warning(
                            "No se pudo upsert el gifter %s: %s", gifter_id, eg
                        )
            break
    except twitchio.HTTPException as e:
        if e.status == 404:
            is_subscriber = False
        else:
            is_subscriber = False
            twitch_msg = extract_twitch_error_message(e)
            prefix = (
                "No se pudo comprobar la suscripción"
                if e.status in (401, 403)
                else "Error al obtener suscripción de Twitch"
            )
            LOGGER.warning(
                "%s para %s (HTTP %s): %s",
                prefix,
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

    is_bot = await bot.user_repo.is_user_bot(user_id, cache=bot.ready_user_cache)

    updated = await bot.user_repo.update_user_roles(
        user_id=user_id,
        channel_id=broadcaster_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=is_subscriber,
        sub_tier=sub_tier,
        gifter_id=gifter_id,
        cache=bot.ready_user_cache,
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

        display_name = await resolve_display_name(bot, user_id, username)

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
