from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools._helpers import format_user_details
from bot_tv.utils.env import OWNER_ID

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_follower_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas relacionadas con la consulta de seguidores
    en la base de datos.
    """

    async def get_follower_stats() -> str:
        """Obtiene estadísticas generales sobre los seguidores en la base de datos."""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_records,
                    SUM(CASE WHEN unfollowed_at IS NULL 
                             THEN 1 ELSE 0 END) as active_followers,
                    SUM(CASE WHEN unfollowed_at IS NOT NULL 
                             THEN 1 ELSE 0 END) as unfollowers
                FROM followers
                WHERE channel_id = ?
            """
            async with bot.app_database.acquire() as conn:
                row = await conn.fetchone(query, (OWNER_ID,))

            if not row or row["total_records"] == 0:
                return "No hay datos de seguidores registrados en la base de datos."

            total = row["total_records"]
            active = row["active_followers"] or 0
            unfollowed = row["unfollowers"] or 0

            return (
                f"Estadísticas de seguidores:\n"
                f"Total histórico registrado: {total}\n"
                f"Seguidores activos: {active}\n"
                f"Dejaron de seguir (unfollow): {unfollowed}"
            )
        except Exception as e:
            LOGGER.error("Error al obtener estadísticas de seguidores: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def search_followers(
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
            query = """
                SELECT u.username, u.display_name, u.nickname,
                       f.followed_at, f.unfollowed_at
                FROM followers f
                JOIN users u ON f.user_id = u.user_id
                WHERE f.channel_id = ? AND (
                    u.username LIKE ? OR 
                    u.display_name LIKE ? OR 
                    u.nickname LIKE ?
                )
            """
            if active_only:
                query += " AND f.unfollowed_at IS NULL"
            query += " ORDER BY f.followed_at DESC LIMIT ?"

            like_pattern = f"%{search_term}%"
            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(
                    query, (OWNER_ID, like_pattern, like_pattern, like_pattern, limit)
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

    async def get_follower_info(username: str) -> str:
        """Obtiene información de seguimiento detallada para un usuario específico
        por su nombre exacto de usuario (username).

        Args:
            username: El nombre de usuario de Twitch exacto (ej: 'twitchdev').
        """
        try:
            query = """
                SELECT u.username, u.display_name, u.nickname,
                       f.followed_at, f.unfollowed_at
                FROM users u
                LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
                WHERE u.username = ? COLLATE NOCASE
            """
            async with bot.app_database.acquire() as conn:
                row = await conn.fetchone(query, (OWNER_ID, username))

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

    async def get_recent_followers(limit: int = 5, active_only: bool = False) -> str:
        """Obtiene una lista de los seguidores registrados más recientemente.

        Args:
            limit: Cantidad de seguidores a mostrar.
            active_only: Si es True, solo muestra seguidores vigentes/activos.
        """
        try:
            limit = max(1, limit)
            query = """
                SELECT u.username, u.display_name, u.nickname,
                       f.followed_at, f.unfollowed_at
                FROM followers f
                JOIN users u ON f.user_id = u.user_id
                WHERE f.channel_id = ?
            """
            if active_only:
                query += " AND f.unfollowed_at IS NULL"
            query += " ORDER BY f.followed_at DESC LIMIT ?"

            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(query, (OWNER_ID, limit))

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

    async def get_recent_unfollowers(limit: int = 5) -> str:
        """Obtiene la lista de los usuarios que han dejado de seguir
        el canal más recientemente.

        Args:
            limit: Cantidad de usuarios a mostrar.
        """
        try:
            limit = max(1, limit)
            query = """
                SELECT u.username, u.display_name, u.nickname,
                       f.followed_at, f.unfollowed_at
                FROM followers f
                JOIN users u ON f.user_id = u.user_id
                WHERE f.channel_id = ? AND f.unfollowed_at IS NOT NULL
                ORDER BY f.unfollowed_at DESC LIMIT ?
            """
            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(query, (OWNER_ID, limit))

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
        get_follower_stats,
        search_followers,
        get_follower_info,
        get_recent_followers,
        get_recent_unfollowers,
    ]
