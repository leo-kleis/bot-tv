from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools._helpers import format_user_details, get_broadcaster_id

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_user_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas relacionadas con la consulta de usuarios
    generales y sus roles.
    """

    async def get_user_info(username: str) -> str:
        """Obtiene información sobre un usuario, incluyendo sus roles en el canal
        (moderador, VIP, suscriptor, bot) y apodo.

        Args:
            username: El nombre de usuario a consultar (ej: 'twitchdev').
        """
        try:
            channel_id = await get_broadcaster_id(bot)
            row = await bot.user_repo.get_user_detail_by_name(username, channel_id)

            if not row:
                return (
                    f"No se encontró información del usuario "
                    f"'{username}' en la base de datos."
                )

            details = format_user_details(
                row["username"],
                row["display_name"],
                row["nickname"],
                row["followed_at"],
                row["unfollowed_at"],
            )

            roles = []
            if row["is_moderator"]:
                roles.append("Moderador")
            if row["is_vip"]:
                roles.append("VIP")
            if row["is_subscriber"]:
                roles.append("Suscriptor")
            if row["is_bot"]:
                roles.append("Bot")
            roles_str = ", ".join(roles) if roles else "Ninguno"

            return f"Información de usuario:\n{details}\nRoles en el canal: {roles_str}"
        except Exception as e:
            LOGGER.error("Error al obtener información detallada del usuario: %s", e)
            return f"Error al consultar base de datos: {e}"

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
        try:
            channel_id = await get_broadcaster_id(bot)
            limit = max(1, limit)
            offset = max(0, offset)
            rows, _ = await bot.user_repo.list_users_with_filters(
                channel_id=channel_id,
                broadcaster_id=channel_id,
                role=role,
                username_search=search_term,
                limit=limit,
                offset=offset,
                cache=bot.user_cache,
            )

            if not rows:
                return (
                    "No se encontraron usuarios registrados en la base de datos "
                    "con los filtros indicados."
                )

            lines = [f"Usuarios registrados ({len(rows)} en esta página):"]
            for r in rows:
                details = format_user_details(
                    r["username"],
                    r["display_name"],
                    r["nickname"],
                    r["followed_at"],
                    r["unfollowed_at"],
                )
                roles = []
                if r["is_moderator"]:
                    roles.append("Mod")
                if r["is_vip"]:
                    roles.append("VIP")
                if r["is_subscriber"]:
                    roles.append("Sub")
                if r["is_bot"]:
                    roles.append("Bot")

                roles_str = f" [{', '.join(roles)}]" if roles else ""
                lines.append(f"- {details}{roles_str}")

            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al listar usuarios: %s", e)
            return f"Error al consultar base de datos: {e}"

    return [
        get_user_info,
        list_users,
    ]
