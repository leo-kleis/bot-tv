"""Acciones de moderación de chat ejecutadas vía TwitchIO."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import twitchio

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


async def _get_broadcaster_channel(bot: Bot) -> twitchio.PartialUser | str:
    """Obtiene el objeto PartialUser del canal (broadcaster) para operaciones Helix."""
    channels = await bot.get_channels()
    if not channels:
        return "No hay canales configurados."

    broadcaster_id = channels[0]["user_id"]
    broadcaster_name = channels[0]["username"]

    return twitchio.PartialUser(
        id=broadcaster_id,
        name=broadcaster_name,
        http=bot._http,
    )


async def action_ban_user(
    bot: Bot, target_username: str, reason: str | None = None
) -> ModerationActionResult:
    """Banea permanentemente a un usuario en el canal de Twitch."""
    res = await resolve_user(bot, target_username)
    if not res.user_id:
        return ModerationActionResult(
            ok=False,
            action="ban",
            target_username=target_username,
            error=res.error or f"No se pudo resolver el ID de '{target_username}'.",
        )

    canal = await _get_broadcaster_channel(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False, action="ban", target_username=target_username, error=canal
        )

    try:
        target_partial = twitchio.PartialUser(id=res.user_id, http=bot._http)
        await canal.ban_user(
            moderator=bot.bot_id,
            user=target_partial,
            reason=reason.strip() if reason and reason.strip() else None,
        )
        LOGGER.info(
            "Usuario '%s' baneado en el canal. Razón: %s", target_username, reason
        )
        return ModerationActionResult(
            ok=True, action="ban", target_username=target_username
        )
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al banear usuario '%s' en Twitch: %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="ban",
            target_username=target_username,
            error=f"Error de Twitch (HTTP {e.status}): {e}",
        )
    except Exception as e:
        LOGGER.exception("Error inesperado al banear a '%s': %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="ban",
            target_username=target_username,
            error=f"Error inesperado: {e}",
        )


async def action_unban_user(bot: Bot, target_username: str) -> ModerationActionResult:
    """Desbanea a un usuario en el canal de Twitch."""
    res = await resolve_user(bot, target_username)
    if not res.user_id:
        return ModerationActionResult(
            ok=False,
            action="unban",
            target_username=target_username,
            error=res.error or f"No se pudo resolver el ID de '{target_username}'.",
        )

    canal = await _get_broadcaster_channel(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False, action="unban", target_username=target_username, error=canal
        )

    try:
        await canal.unban_user(
            moderator=bot.bot_id,
            user_id=res.user_id,
        )
        LOGGER.info("Usuario '%s' desbaneado en el canal.", target_username)
        return ModerationActionResult(
            ok=True, action="unban", target_username=target_username
        )
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al desbanear usuario '%s': %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="unban",
            target_username=target_username,
            error=f"Error de Twitch (HTTP {e.status}): {e}",
        )
    except Exception as e:
        LOGGER.exception("Error inesperado al desbanear a '%s': %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="unban",
            target_username=target_username,
            error=f"Error inesperado: {e}",
        )


async def action_delete_messages(
    bot: Bot, target_username: str, message_id: str | None = None
) -> ModerationActionResult:
    """Elimina un mensaje específico o limpia todo el chat público.

    Si message_id es None, ejecuta /clear del chat.
    NOTA: NO borra nada de la base de datos local PostgreSQL.
    """
    canal = await _get_broadcaster_channel(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False,
            action="delete_message",
            target_username=target_username,
            error=canal,
        )

    try:
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
        return ModerationActionResult(
            ok=True, action="delete_message", target_username=target_username
        )
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al eliminar mensajes en Twitch: %s", e)
        return ModerationActionResult(
            ok=False,
            action="delete_message",
            target_username=target_username,
            error=f"Error de Twitch (HTTP {e.status}): {e}",
        )
    except Exception as e:
        LOGGER.exception("Error inesperado al borrar mensajes: %s", e)
        return ModerationActionResult(
            ok=False,
            action="delete_message",
            target_username=target_username,
            error=f"Error inesperado: {e}",
        )


async def action_purge_user(bot: Bot, target_username: str) -> ModerationActionResult:
    """Aplica timeout de 1s a un usuario para purgar sus mensajes recientes.

    NOTA: NO borra nada de la base de datos local PostgreSQL.
    """
    res = await resolve_user(bot, target_username)
    if not res.user_id:
        return ModerationActionResult(
            ok=False,
            action="purge",
            target_username=target_username,
            error=res.error or f"No se pudo resolver el ID de '{target_username}'.",
        )

    canal = await _get_broadcaster_channel(bot)
    if isinstance(canal, str):
        return ModerationActionResult(
            ok=False, action="purge", target_username=target_username, error=canal
        )

    try:
        target_partial = twitchio.PartialUser(id=res.user_id, http=bot._http)
        await canal.timeout_user(
            moderator=bot.bot_id,
            user=target_partial,
            duration=1,
            reason="Purga rápida de mensajes",
        )
        LOGGER.info(
            "Purga de mensajes de '%s' ejecutada (timeout 1s).", target_username
        )
        return ModerationActionResult(
            ok=True, action="purge", target_username=target_username
        )
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al purgar usuario '%s' en Twitch: %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="purge",
            target_username=target_username,
            error=f"Error de Twitch (HTTP {e.status}): {e}",
        )
    except Exception as e:
        LOGGER.exception("Error inesperado al purgar a '%s': %s", target_username, e)
        return ModerationActionResult(
            ok=False,
            action="purge",
            target_username=target_username,
            error=f"Error inesperado: {e}",
        )
