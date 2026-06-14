from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools._helpers import format_user_details
from bot_tv.utils.env import OWNER_ID
from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_chat_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas relacionadas con la consulta del historial
    y estadísticas del chat.
    """

    async def get_user_chat_history(username: str, limit: int = 20) -> str:
        """Obtiene los mensajes de chat más recientes enviados por
        un usuario específico.

        Args:
            username: El nombre de usuario a consultar.
            limit: Cantidad máxima de mensajes a retornar.
        """
        try:
            limit = max(1, limit)
            # Primero, busquemos el usuario y su estado de seguidor
            user_query = """
                SELECT u.user_id, u.username, u.display_name, u.nickname,
                       f.followed_at, f.unfollowed_at
                FROM users u
                LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
                WHERE u.username = ? COLLATE NOCASE
            """
            async with bot.app_database.acquire() as conn:
                user_row = await conn.fetchone(user_query, (OWNER_ID, username))

            if not user_row:
                return f"No se encontró al usuario '{username}' en la base de datos."

            # Ahora buscar historial de mensajes
            messages_query = """
                SELECT message, timestamp
                FROM chat_history
                WHERE channel_id = ? AND user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """
            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(
                    messages_query, (OWNER_ID, user_row["user_id"], limit)
                )

            details = format_user_details(
                user_row["username"],
                user_row["display_name"],
                user_row["nickname"],
                user_row["followed_at"],
                user_row["unfollowed_at"],
            )

            if not rows:
                return (
                    f"Historial de chat para {details}:\nNo hay mensajes registrados."
                )

            lines = [f"Historial de chat para {details}:"]
            for r in rows:
                lines.append(f"- [{format_date(r['timestamp'])}] {r['message']}")
            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener historial de chat de usuario: %s", e)
            return f"Error al consultar base de datos: {e}"

    async def get_chat_stats() -> str:
        """Obtiene estadísticas generales del chat, incluyendo total de mensajes,
        usuarios únicos y top chatters.
        """
        try:
            stats_query = """
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT user_id) as unique_users
                FROM chat_history
                WHERE channel_id = ?
            """
            top_query = """
                SELECT u.username, u.display_name, u.nickname, COUNT(c.id) as msg_count
                FROM chat_history c
                JOIN users u ON c.user_id = u.user_id
                WHERE c.channel_id = ?
                GROUP BY c.user_id
                ORDER BY msg_count DESC LIMIT 5
            """

            async with bot.app_database.acquire() as conn:
                stats_row = await conn.fetchone(stats_query, (OWNER_ID,))
                top_rows = await conn.fetchall(top_query, (OWNER_ID,))

            if not stats_row or stats_row["total_messages"] == 0:
                return "No hay estadísticas de chat registradas aún."

            total = stats_row["total_messages"]
            users = stats_row["unique_users"]

            lines = [
                f"Estadísticas del Chat:\n"
                f"Mensajes totales guardados: {total}\n"
                f"Usuarios únicos activos: {users}\n\n"
                f"Top 5 usuarios más activos:"
            ]
            for idx, r in enumerate(top_rows, 1):
                name = r["display_name"] or r["username"]
                if r["nickname"]:
                    name = f"{name} ({r['nickname']})"
                lines.append(f"{idx}. {name}: {r['msg_count']} mensajes")

            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener estadísticas de chat: %s", e)
            return f"Error al consultar base de datos: {e}"

    return [
        get_user_chat_history,
        get_chat_stats,
    ]
