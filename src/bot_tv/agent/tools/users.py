from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_tv.agent.tools._helpers import (
    AgentToolFn,
    clamp_limit,
    clamp_offset,
    extract_user_roles,
    format_user_details_row,
    handle_tool_error,
    normalize_role_filter,
    normalize_username,
    require_broadcaster_id,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_user_tools(bot: Bot) -> list[AgentToolFn]:
    """Construye las herramientas relacionadas con la consulta de usuarios
    generales y sus roles.
    """

    async def get_user_info(username: str) -> str:
        """Obtiene información sobre un usuario, incluyendo sus roles en el canal
        (moderador, VIP, suscriptor, bot) y apodo.

        Args:
            username: El nombre de usuario a consultar (ej: 'twitchdev').
        """
        clean_username, user_err = normalize_username(username)
        if user_err or clean_username is None:
            return user_err or "El nombre de usuario no puede estar vacío."

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."

            row = await bot.user_repo.get_user_detail_by_name(
                clean_username, channel_id, cache=bot.ready_user_cache
            )

            if not row:
                return (
                    f"No se encontró información del usuario "
                    f"'{clean_username}' en la base de datos."
                )

            details = format_user_details_row(row)
            roles = extract_user_roles(row, short=False)
            roles_str = ", ".join(roles) if roles else "Ninguno"

            return f"Información de usuario:\n{details}\nRoles en el canal: {roles_str}"
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener información detallada del usuario", exc
            )

    async def list_users(
        role: str | None = None,
        search_term: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> str:
        """Lista usuarios registrados en la base de datos aplicando filtros.

        Args:
            role: Filtrar por un rol específico en el canal.
                Valores válidos: 'bot', 'moderator', 'vip', 'subscriber' (opcional).
            search_term: Término de búsqueda para filtrar por nombre de usuario,
                display name o apodo (opcional).
            limit: Cantidad de registros a retornar (por defecto: 10).
            offset: Desplazamiento para paginación (por defecto: 0).
        """
        clean_role, role_err = normalize_role_filter(role)
        if role_err:
            return role_err

        clean_search = search_term.strip() if search_term else None
        if clean_search == "":
            clean_search = None

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit)
            safe_offset = clamp_offset(offset)

            rows, _ = await bot.user_repo.list_users_with_filters(
                channel_id=channel_id,
                broadcaster_id=channel_id,
                role=clean_role,
                username_search=clean_search,
                limit=safe_limit,
                offset=safe_offset,
                cache=bot.ready_user_cache,
            )

            if not rows:
                return (
                    "No se encontraron usuarios registrados en la base de datos "
                    "con los filtros indicados."
                )

            lines: list[str] = [f"Usuarios registrados ({len(rows)} en esta página):"]
            for r in rows:
                details = format_user_details_row(r)
                roles = extract_user_roles(r, short=True)
                roles_str = f" [{', '.join(roles)}]" if roles else ""
                lines.append(f"- {details}{roles_str}")

            return "\n".join(lines)
        except Exception as exc:
            return handle_tool_error(LOGGER, "Error al listar usuarios", exc)

    return [
        get_user_info,
        list_users,
    ]
