from __future__ import annotations

import datetime
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

    async def get_chat_messages(
        username: str | None = None,
        search_term: str | None = None,
        role: str | None = None,
        hours_ago: float | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> str:
        """Obtiene y busca mensajes de chat en el historial del canal.

        Permite aplicar filtros opcionales para buscar mensajes específicos por
        usuario, palabras clave, rol del usuario, antigüedad o rangos de fecha.

        Args:
            username: Filtrar mensajes por un nombre de usuario específico (opcional).
            search_term: Buscar mensajes que contengan este término (opcional).
            role: Filtrar mensajes por el rol del usuario en el canal.
                Valores permitidos: 'bot', 'moderator', 'vip', 'subscriber' (opcional).
            hours_ago: Buscar mensajes enviados en las últimas X horas (opcional).
            since: Fecha y hora de inicio en formato ISO 8601
                (ej: '2026-06-14T15:00:00') para buscar mensajes desde ese
                momento (opcional).
            until: Fecha y hora de fin en formato ISO 8601
                (ej: '2026-06-14T18:00:00') para buscar mensajes hasta ese
                momento (opcional).
            limit: Cantidad máxima de mensajes a retornar.
        """
        try:
            limit = max(1, limit)
            where_clauses = ["c.channel_id = ?"]
            params: list[Any] = [OWNER_ID]

            if hours_ago is not None:
                since_time = (
                    datetime.datetime.now(datetime.UTC)
                    - datetime.timedelta(hours=hours_ago)
                ).isoformat()
                where_clauses.append("c.timestamp >= ?")
                params.append(since_time)

            if since:
                since_iso = since.replace(" ", "T")
                where_clauses.append("c.timestamp >= ?")
                params.append(since_iso)

            if until:
                until_iso = until.replace(" ", "T")
                where_clauses.append("c.timestamp <= ?")
                params.append(until_iso)

            user_details = ""
            if username:
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
                    return (
                        f"No se encontró al usuario '{username}' en la base de datos."
                    )

                where_clauses.append("u.username = ? COLLATE NOCASE")
                params.append(username)

                user_details = format_user_details(
                    user_row["username"],
                    user_row["display_name"],
                    user_row["nickname"],
                    user_row["followed_at"],
                    user_row["unfollowed_at"],
                )

            if search_term:
                where_clauses.append("c.message LIKE ?")
                params.append(f"%{search_term}%")

            if role:
                role_clean = role.lower()
                if role_clean in ("bot", "bots"):
                    where_clauses.append("u.is_bot = 1")
                elif role_clean in ("moderator", "moderador", "mods", "mod"):
                    where_clauses.append("u.is_moderator = 1")
                elif role_clean in ("vip", "vips"):
                    where_clauses.append("u.is_vip = 1")
                elif role_clean in (
                    "subscriber",
                    "suscriptor",
                    "subscribers",
                    "sub",
                    "subs",
                ):
                    where_clauses.append("u.is_subscriber = 1")
                else:
                    return (
                        f"Rol '{role}' no reconocido. Roles válidos: "
                        "bot, moderator, vip, subscriber."
                    )

            query = f"""
                SELECT u.username, u.display_name, u.nickname, c.message, c.timestamp
                FROM chat_history c
                JOIN users u ON c.user_id = u.user_id
                WHERE {" AND ".join(where_clauses)}
                ORDER BY c.timestamp DESC LIMIT ?
            """
            params.append(limit)

            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(query, tuple(params))

            if not rows:
                if user_details:
                    return (
                        f"Historial de chat para {user_details}:\n"
                        f"No hay mensajes registrados."
                    )
                return (
                    "No se encontraron mensajes registrados en el chat "
                    "con los filtros indicados."
                )

            if user_details:
                header = f"Historial de chat para {user_details}:"
            else:
                header = "Mensajes de chat encontrados:"

            lines = [header]
            for r in reversed(rows):
                name = r["display_name"] or r["username"]
                if r["nickname"]:
                    name = f"{name} ({r['nickname']})"
                lines.append(
                    f"- [{format_date(r['timestamp'])}] {name}: {r['message']}"
                )

            return "\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener mensajes del chat: %s", e)
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
        get_chat_messages,
        get_chat_stats,
    ]
