from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools._helpers import format_user_details
from bot_tv.utils.env import OWNER_ID

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_channel_user_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas relacionadas con la consulta de usuarios y seguidores
    del canal en la base de datos.
    """

    async def get_channel_user_stats() -> str:
        """Obtiene estadísticas generales sobre los seguidores en la base de datos."""
        try:
            row = await bot.channel_user_repo.get_follower_stats(OWNER_ID)
            if not row:
                return "No hay datos de seguidores registrados en la base de datos."

            total = row["total_records"]
            active = row["active_followers"]
            unfollowed = row["unfollowers"]

            return (
                f"Estadísticas de seguidores:\n"
                f"Total histórico registrado: {total}\n"
                f"Seguidores activos: {active}\n"
                f"Dejaron de seguir (unfollow): {unfollowed}"
            )
        except Exception as e:
            LOGGER.error("Error al obtener estadísticas de seguidores: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def search_channel_users(
        search_term: str, active_only: bool = False, limit: int = 10
    ) -> str:
        """Busca seguidores en la base de datos por coincidencia de nombre.

        Args:
            search_term: Término de búsqueda (coincide con username,
                display_name o nickname).
            active_only: Si es True, filtra para mostrar solo seguidores activos.
            limit: Límite de resultados a retornar.
        """
        try:
            limit = max(1, limit)
            rows = await bot.channel_user_repo.search_followers(
                channel_id=OWNER_ID,
                search_term=search_term,
                active_only=active_only,
                limit=limit,
            )

            if not rows:
                suffix = " activos" if active_only else ""
                return (
                    f"No se encontraron seguidores{suffix} "
                    f"con el término '{search_term}'."
                )

            lines = [f"Resultados de búsqueda ({len(rows)} encontrados):"]
            for r in rows:
                user_detail = format_user_details(
                    r["username"],
                    r["display_name"],
                    r["nickname"],
                    r["followed_at"],
                    r["unfollowed_at"],
                )
                lines.append(f"- {user_detail}")
            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al buscar seguidores: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def get_channel_user_info(username: str) -> str:
        """Obtiene información detallada de seguimiento y roles de un usuario
        por su nombre de usuario exacto (username).

        Args:
            username: El nombre de usuario de Twitch exacto (ej: 'twitchdev').
        """
        try:
            row = await bot.user_repo.get_user_detail_by_name(username, OWNER_ID)
            if not row:
                return (
                    f"No se encontró información del usuario "
                    f"'{username}' en la base de datos."
                )

            return format_user_details(
                row["username"],
                row["display_name"],
                row["nickname"],
                row["followed_at"],
                row["unfollowed_at"],
            )
        except Exception as e:
            LOGGER.error("Error al obtener información del seguidor: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def get_recent_channel_users(
        limit: int = 5, active_only: bool = False
    ) -> str:
        """Obtiene una lista de los seguidores registrados más recientemente.

        Args:
            limit: Cantidad de seguidores a mostrar.
            active_only: Si es True, solo muestra seguidores vigentes/activos.
        """
        try:
            limit = max(1, limit)
            rows = await bot.channel_user_repo.get_recent_followers(
                channel_id=OWNER_ID, limit=limit, active_only=active_only
            )

            if not rows:
                suffix = " activos" if active_only else ""
                return f"No se encontraron seguidores{suffix} en la base de datos."

            suffix = " activos" if active_only else ""
            lines = [f"Últimos {len(rows)} seguidores{suffix}:"]
            for r in rows:
                user_detail = format_user_details(
                    r["username"],
                    r["display_name"],
                    r["nickname"],
                    r["followed_at"],
                    r["unfollowed_at"],
                )
                lines.append(f"- {user_detail}")
            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener seguidores recientes: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def get_recent_channel_unfollowers(limit: int = 5) -> str:
        """Obtiene la lista de los usuarios que han dejado de seguir
        el canal más recientemente.

        Args:
            limit: Cantidad de usuarios a mostrar.
        """
        try:
            limit = max(1, limit)
            rows = await bot.channel_user_repo.get_recent_unfollowers(
                channel_id=OWNER_ID, limit=limit
            )

            if not rows:
                return (
                    "No hay registros recientes de usuarios que hayan dejado de seguir."
                )

            lines = [f"Últimos {len(rows)} usuarios que dejaron de seguir:"]
            for r in rows:
                user_detail = format_user_details(
                    r["username"],
                    r["display_name"],
                    r["nickname"],
                    r["followed_at"],
                    r["unfollowed_at"],
                )
                lines.append(f"- {user_detail}")
            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener unfollowers recientes: %s", e)
            return f"Error al consultar base de datos: {e}"

    return [
        get_channel_user_stats,
        search_channel_users,
        get_channel_user_info,
        get_recent_channel_users,
        get_recent_channel_unfollowers,
    ]
