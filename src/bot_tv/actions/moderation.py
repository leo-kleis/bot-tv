"""Acciones de moderación de chat ejecutadas vía TwitchIO."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import twitchio

from bot_tv.actions._helpers import get_broadcaster_partial
from bot_tv.actions.users import resolve_user

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


@dataclass
class ModerationActionResult:
    """Resultado de una acción de moderación."""

    ok: bool
    action: str
    target_username: str
    error: str | None = None


@dataclass
class UserBanStatus:
    """Estado de moderación (ban/timeout) de un usuario en el canal."""

    is_banned: bool = False
    permanent: bool = False
    expires_at: str | None = None
    reason: str | None = None
    created_at: str | None = None
    moderator_id: str | None = None
    moderator_name: str | None = None


async def _resolve_target_and_channel(
    bot: Bot, action: str, target_username: str
) -> tuple[str, twitchio.PartialUser] | ModerationActionResult:
    """Resuelve el user_id objetivo y el PartialUser del broadcaster."""
    res = await resolve_user(bot, target_username)
    if not res.user_id:
        return ModerationActionResult(
            ok=False,
            action=action,
            target_username=target_username,
            error=res.error or f"No se pudo resolver el ID de '{target_username}'.",
        )

    canal = await get_broadcaster_partial(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False, action=action, target_username=target_username, error=canal
        )

    return res.user_id, canal


async def _run_moderation_call(
    action: str,
    target_username: str,
    operation: Callable[[], Awaitable[None]],
    *,
    http_log_context: str,
    unexpected_log_context: str,
) -> ModerationActionResult:
    """Ejecuta una llamada de moderación en Twitch mapeando errores."""
    try:
        await operation()
        return ModerationActionResult(
            ok=True, action=action, target_username=target_username
        )
    except twitchio.HTTPException as e:
        LOGGER.error("%s '%s': %s", http_log_context, target_username, e)
        return ModerationActionResult(
            ok=False,
            action=action,
            target_username=target_username,
            error=f"Error de Twitch (HTTP {e.status}).",
        )
    except Exception as e:
        LOGGER.exception("%s '%s': %s", unexpected_log_context, target_username, e)
        return ModerationActionResult(
            ok=False,
            action=action,
            target_username=target_username,
            error="Error inesperado al ejecutar la acción de moderación.",
        )


async def action_ban_user(
    bot: Bot, target_username: str, reason: str | None = None
) -> ModerationActionResult:
    """Banea permanentemente a un usuario en el canal de Twitch."""
    resolved = await _resolve_target_and_channel(bot, "ban", target_username)
    if isinstance(resolved, ModerationActionResult):
        return resolved
    user_id, canal = resolved

    async def _ban() -> None:
        target_partial = twitchio.PartialUser(id=user_id, http=bot.twitch_http)
        await canal.ban_user(
            moderator=bot.bot_id,
            user=target_partial,
            reason=reason.strip() if reason and reason.strip() else None,
        )
        LOGGER.info(
            "Usuario '%s' baneado en el canal. Razón: %s", target_username, reason
        )

    return await _run_moderation_call(
        "ban",
        target_username,
        _ban,
        http_log_context="Fallo al banear usuario en Twitch",
        unexpected_log_context="Error inesperado al banear",
    )


async def action_unban_user(bot: Bot, target_username: str) -> ModerationActionResult:
    """Desbanea a un usuario en el canal de Twitch."""
    resolved = await _resolve_target_and_channel(bot, "unban", target_username)
    if isinstance(resolved, ModerationActionResult):
        return resolved
    user_id, canal = resolved

    async def _unban() -> None:
        await canal.unban_user(moderator=bot.bot_id, user_id=user_id)
        LOGGER.info("Usuario '%s' desbaneado en el canal.", target_username)

    return await _run_moderation_call(
        "unban",
        target_username,
        _unban,
        http_log_context="Fallo al desbanear usuario",
        unexpected_log_context="Error inesperado al desbanear",
    )


async def action_get_user_ban_status(bot: Bot, target_username: str) -> UserBanStatus:
    """Consulta en tiempo real a la API de Twitch si un usuario está baneado
    en el canal.
    """
    res = await resolve_user(bot, target_username)
    if not res.user_id:
        return UserBanStatus(is_banned=False)

    canal = await get_broadcaster_partial(bot)
    if isinstance(canal, str):
        return UserBanStatus(is_banned=False)

    # El broadcaster y el bot no pueden estar baneados en su propio canal
    if res.user_id in (canal.id, bot.bot_id):
        return UserBanStatus(is_banned=False)

    try:
        async for banned_user in canal.fetch_banned_user(
            user_ids=[res.user_id], first=1, max_results=1
        ):
            expires_at_iso = (
                banned_user.expires_at.isoformat() if banned_user.expires_at else None
            )
            created_at_iso = (
                banned_user.created_at.isoformat() if banned_user.created_at else None
            )
            return UserBanStatus(
                is_banned=True,
                permanent=banned_user.expires_at is None,
                expires_at=expires_at_iso,
                reason=banned_user.reason or None,
                created_at=created_at_iso,
                moderator_id=banned_user.moderator.id
                if banned_user.moderator
                else None,
                moderator_name=banned_user.moderator.name
                if banned_user.moderator
                else None,
            )
        return UserBanStatus(is_banned=False)
    except twitchio.HTTPException as e:
        LOGGER.warning(
            "No se pudo consultar el estado de baneo de '%s' (HTTP %s): %s",
            target_username,
            e.status,
            e,
        )
        return UserBanStatus(is_banned=False)
    except Exception as e:
        LOGGER.warning(
            "Error al consultar el estado de baneo de '%s': %s",
            target_username,
            e,
        )
        return UserBanStatus(is_banned=False)


async def action_delete_messages(
    bot: Bot, target_username: str, message_id: str | None = None
) -> ModerationActionResult:
    """Elimina un mensaje específico o limpia todo el chat público.

    Si message_id es None, ejecuta /clear del chat.
    NOTA: NO borra nada de la base de datos local PostgreSQL.
    """
    canal = await get_broadcaster_partial(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False,
            action="delete_message",
            target_username=target_username,
            error=canal,
        )

    async def _delete() -> None:
        await canal.delete_chat_messages(
            moderator=bot.bot_id,
            message_id=message_id if message_id and message_id.strip() else None,
        )
        action_name = (
            "Limpieza de chat completo"
            if not message_id
            else f"Mensaje {message_id} eliminado"
        )
        LOGGER.info("%s ejecutado en Twitch para '%s'", action_name, target_username)

    return await _run_moderation_call(
        "delete_message",
        target_username,
        _delete,
        http_log_context="Fallo al eliminar mensajes en Twitch para",
        unexpected_log_context="Error inesperado al borrar mensajes de",
    )


async def action_purge_user(bot: Bot, target_username: str) -> ModerationActionResult:
    """Aplica timeout de 1s a un usuario para purgar sus mensajes recientes.

    NOTA: NO borra nada de la base de datos local PostgreSQL.
    """
    resolved = await _resolve_target_and_channel(bot, "purge", target_username)
    if isinstance(resolved, ModerationActionResult):
        return resolved
    user_id, canal = resolved

    async def _purge() -> None:
        target_partial = twitchio.PartialUser(id=user_id, http=bot.twitch_http)
        await canal.timeout_user(
            moderator=bot.bot_id,
            user=target_partial,
            duration=1,
            reason="Purga rápida de mensajes",
        )
        LOGGER.info(
            "Purga de mensajes de '%s' ejecutada (timeout 1s).", target_username
        )

    return await _run_moderation_call(
        "purge",
        target_username,
        _purge,
        http_log_context="Fallo al purgar usuario en Twitch",
        unexpected_log_context="Error inesperado al purgar",
    )
