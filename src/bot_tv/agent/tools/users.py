from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools._helpers import format_user_details
from bot_tv.utils.env import OWNER_ID

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
            row = await bot.user_repo.get_user_detail_by_name(username, OWNER_ID)

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
        has_nickname: bool | None = None,
        limit: int = 20,
    ) -> str:
        """Obtiene una lista de usuarios registrados en el canal con filtros
        opcionales por rol o presencia de apodo/nickname.

        Args:
            role: Filtrar por rol. Valores permitidos: 'bot', 'moderator',
                'vip', 'subscriber'.
            has_nickname: Si es True, muestra solo usuarios con apodo.
            limit: Límite de resultados a retornar.
        """
        try:
            limit = max(1, limit)
            if role:
                role_clean = role.lower()
                valid_roles = {
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
                if role_clean not in valid_roles:
                    return (
                        f"Rol '{role}' no reconocido. Roles válidos: "
                        "bot, moderator, vip, subscriber."
                    )

            rows = await bot.user_repo.list_users_with_filters(
                channel_id=OWNER_ID,
                role=role,
                has_nickname=has_nickname,
                limit=limit,
            )

            if not rows:
                return (
                    "No se encontraron usuarios que coincidan "
                    "con los filtros especificados."
                )

            lines = [f"Usuarios encontrados ({len(rows)}):"]
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
