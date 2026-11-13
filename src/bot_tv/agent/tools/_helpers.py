from __future__ import annotations

import html
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

import asyncpg
import twitchio

from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot

type AgentToolFn = Callable[..., Any]

DEFAULT_TOOL_LIMIT: Final[int] = 10
MAX_TOOL_LIMIT: Final[int] = 100
MAX_VOD_LIMIT: Final[int] = 25

VALID_ROLE_FILTERS: Final[frozenset[str]] = frozenset(
    {
        "bot",
        "bots",
        "moderator",
        "moderador",
        "mods",
        "mod",
        "vip",
        "vips",
        "subscriber",
        "suscriptor",
        "subscribers",
        "sub",
        "subs",
    }
)


def sanitize_untrusted_text(text: str | None) -> str:
    """Escapa delimitadores XML (< y >) en texto no confiable para prevenir
    inyección de prompts indirecta al cerrar etiquetas de datos.
    """
    if not text:
        return ""
    return html.escape(text, quote=False)


async def get_broadcaster_id(bot: Bot) -> str:
    """Obtiene el ID del broadcaster de forma segura (OWNER_ID o primer canal)."""
    if bot.owner_id and bot.owner_id.strip():
        return bot.owner_id.strip()
    channels = await bot.get_channels()
    if channels:
        return channels[0]["user_id"]
    return ""


async def require_broadcaster_id(bot: Bot) -> tuple[str | None, str | None]:
    """Obtiene el ID del broadcaster o retorna un error legible si falta."""
    channel_id = await get_broadcaster_id(bot)
    if not channel_id:
        return None, "No hay ningún canal configurado en el bot."
    return channel_id, None


def clamp_limit(limit: int, *, minimum: int = 1, maximum: int = MAX_TOOL_LIMIT) -> int:
    """Acota el parámetro limit al rango permitido."""
    return max(minimum, min(limit, maximum))


def clamp_offset(offset: int) -> int:
    """Asegura que offset no sea negativo."""
    return max(0, offset)


def normalize_non_empty(value: str, field_name: str) -> tuple[str | None, str | None]:
    """Valida que una cadena no esté vacía tras limpiar espacios."""
    cleaned = value.strip()
    if not cleaned:
        return None, f"El parámetro '{field_name}' no puede estar vacío."
    return cleaned, None


def normalize_username(username: str) -> tuple[str | None, str | None]:
    """Normaliza un nombre de usuario de Twitch quitando espacios y '@' inicial."""
    cleaned = username.strip().lstrip("@").strip()
    if not cleaned:
        return None, "El nombre de usuario no puede estar vacío."
    return cleaned, None


def normalize_role_filter(role: str | None) -> tuple[str | None, str | None]:
    """Valida el filtro opcional de rol de canal."""
    if role is None:
        return None, None
    cleaned = role.strip().lower()
    if not cleaned:
        return None, None
    if cleaned not in VALID_ROLE_FILTERS:
        return None, (
            f"Rol inválido '{role}'. Valores permitidos: "
            "'bot', 'moderator', 'vip', 'subscriber'."
        )
    return cleaned, None


def normalize_iso_timestamp(
    value: str | None, field_name: str
) -> tuple[str | None, str | None]:
    """Normaliza y valida un timestamp ISO 8601 opcional."""
    if value is None:
        return None, None
    cleaned = value.strip()
    if not cleaned:
        return None, None
    normalized = cleaned.replace(" ", "T")
    parse_candidate = (
        f"{normalized[:-1]}+00:00" if normalized.endswith("Z") else normalized
    )
    try:
        datetime.fromisoformat(parse_candidate)
    except ValueError:
        return None, (
            f"Formato de fecha inválido en '{field_name}': '{value}'. "
            "Usa formato ISO 8601 (ej: '2026-06-14T15:00:00')."
        )
    return normalized, None


def format_user_display_name(
    username: str, display_name: str | None, nickname: str | None
) -> str:
    """Formatea de forma segura el nombre visible y apodo de un usuario."""
    safe_name = sanitize_untrusted_text(display_name or username)
    if nickname:
        safe_nick = sanitize_untrusted_text(nickname)
        return f"{safe_name} ({safe_nick})"
    return safe_name


def format_user_details(
    username: str,
    display_name: str | None,
    nickname: str | None,
    followed_at: str | None,
    unfollowed_at: str | None,
) -> str:
    """Formatea la información detallada de un usuario y su estado de seguimiento."""
    name_str = format_user_display_name(username, display_name, nickname)

    if followed_at:
        if unfollowed_at:
            return (
                f"{name_str} - No es seguidor (Siguió el: "
                f"{format_date(followed_at)} - Dejó de seguir el: "
                f"{format_date(unfollowed_at)})"
            )
        return f"{name_str} - Seguidor desde: {format_date(followed_at)}"
    return f"{name_str} - No es seguidor"


def format_user_details_row(row: Mapping[str, Any]) -> str:
    """Formatea un diccionario de fila de usuario delegando a format_user_details."""
    return format_user_details(
        str(row["username"]),
        row.get("display_name"),
        row.get("nickname"),
        row.get("followed_at"),
        row.get("unfollowed_at"),
    )


def extract_user_roles(row: Mapping[str, Any], *, short: bool = False) -> list[str]:
    """Extrae la lista de roles legibles de una fila de usuario."""
    roles: list[str] = []
    if row.get("is_moderator"):
        roles.append("Mod" if short else "Moderador")
    if row.get("is_vip"):
        roles.append("VIP")
    if row.get("is_subscriber"):
        roles.append("Sub" if short else "Suscriptor")
    if row.get("is_bot"):
        roles.append("Bot")
    return roles


def handle_tool_error(
    logger: logging.Logger,
    context: str,
    exc: Exception,
    *,
    prefix: str = "Error al consultar base de datos",
) -> str:
    """Registra errores de herramientas diferenciando fallos esperados e inesperados."""
    if isinstance(exc, (ValueError, asyncpg.PostgresError, twitchio.HTTPException)):
        logger.error("%s: %s", context, exc)
    else:
        logger.exception("%s: %s", context, exc)
    return f"{prefix}: {exc}"
