from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.utils.env import OWNER_ID
from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_agent_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas del agente capturando la referencia al bot."""

    async def change_stream_title(new_title: str) -> str:
        """Cambia el título del stream actual del canal.

        Args:
            new_title: El nuevo título para el stream.
        """
        try:
            # Obtener título viejo si está en vivo
            old_title = "Desconocido (Stream offline o sin título)"
            streams = bot.fetch_streams(user_ids=[int(OWNER_ID)])
            async for stream in streams:
                if stream.title:
                    old_title = stream.title
                break
            else:
                # Si está offline, intentar buscar la info del canal
                channel_info = await bot.fetch_channel(broadcaster_id=OWNER_ID)
                if channel_info and channel_info.title:
                    old_title = channel_info.title

            # Modificar stream
            canal = bot.create_partialuser(user_id=OWNER_ID)
            # pyrefly: ignore [missing-attribute]
            await canal.modify_stream(title=new_title, token_for=OWNER_ID)
            return (
                f"Título cambiado con éxito.\n"
                f"Antes: '{old_title}'\n"
                f"Después: '{new_title}'"
            )
        except Exception as e:
            LOGGER.error("Error al cambiar título del stream: %s", e)
            return f"Error al cambiar el título: {e}"

    async def change_stream_category(category_name: str) -> str:
        """Cambia la categoría/juego del stream actual del canal.

        Args:
            category_name: El nombre de la nueva categoría o juego en Twitch.
        """
        try:
            # Buscar el juego en Twitch
            games = await bot.fetch_games(names=[category_name])
            if not games:
                return (
                    f"No se pudo encontrar la categoría '{category_name}' "
                    f"en Twitch. Verifica el nombre."
                )

            target_game = games[0]
            game_id = target_game.id
            resolved_name = target_game.name

            # Obtener categoría vieja
            old_category = "Desconocida"
            streams = bot.fetch_streams(user_ids=[int(OWNER_ID)])
            async for stream in streams:
                if stream.game_name:
                    old_category = stream.game_name
                break
            else:
                channel_info = await bot.fetch_channel(broadcaster_id=OWNER_ID)
                if channel_info and channel_info.game_name:
                    old_category = channel_info.game_name

            # Modificar stream
            canal = bot.create_partialuser(user_id=OWNER_ID)
            # pyrefly: ignore [missing-attribute]
            await canal.modify_stream(game_id=game_id, token_for=OWNER_ID)
            return (
                f"Categoría cambiada con éxito.\n"
                f"Antes: '{old_category}'\n"
                f"Después: '{resolved_name}'"
            )
        except Exception as e:
            LOGGER.error("Error al cambiar categoría del stream: %s", e)
            return f"Error al cambiar la categoría: {e}"

    async def get_stream_info() -> str:
        """Obtiene información sobre el stream actual del canal.

        Retorna título, categoría y cantidad de espectadores actuales.
        """
        try:
            streams = bot.fetch_streams(user_ids=[int(OWNER_ID)])
            async for stream in streams:
                return (
                    f"El canal está EN VIVO.\n"
                    f"Título: '{stream.title}'\n"
                    f"Categoría: '{stream.game_name}'\n"
                    f"Espectadores: {stream.viewer_count}"
                )

            # Si no está en vivo, buscar info de canal
            channel_info = await bot.fetch_channel(broadcaster_id=OWNER_ID)
            if channel_info:
                return (
                    f"El canal está OFFLINE.\n"
                    f"Último título: '{channel_info.title}'\n"
                    f"Última categoría: '{channel_info.game_name}'"
                )
            return "No se pudo obtener la información del canal."
        except Exception as e:
            LOGGER.error("Error al obtener información de stream: %s", e)
            return f"Error al consultar información de stream: {e}"

    def format_user_details(
        username: str,
        display_name: str | None,
        nickname: str | None,
        followed_at: str | None,
        unfollowed_at: str | None,
    ) -> str:
        name = display_name or username
        name_str = f"{name} ({nickname})" if nickname else name

        if followed_at:
            if unfollowed_at:
                return (
                    f"{name_str} - No es seguidor (Siguió el: "
                    f"{format_date(followed_at)} - Dejó de seguir el: "
                    f"{format_date(unfollowed_at)})"
                )
            else:
                return f"{name_str} - Seguidor desde: {format_date(followed_at)}"
        else:
            return f"{name_str} - No es seguidor"

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

    async def get_user_info(username: str) -> str:
        """Obtiene información sobre un usuario, incluyendo sus roles en el canal
        (moderador, VIP, suscriptor, bot) y apodo.

        Args:
            username: El nombre de usuario a consultar (ej: 'twitchdev').
        """
        try:
            query = """
                SELECT u.username, u.display_name, u.nickname, u.is_bot,
                       u.is_moderator, u.is_vip, u.is_subscriber,
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
            where_clauses = []
            params: list[Any] = [OWNER_ID]

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

            if has_nickname is not None:
                if has_nickname:
                    where_clauses.append("u.nickname IS NOT NULL AND u.nickname != ''")
                else:
                    where_clauses.append("(u.nickname IS NULL OR u.nickname = '')")

            query = """
                SELECT u.username, u.display_name, u.nickname, u.is_bot,
                       u.is_moderator, u.is_vip, u.is_subscriber,
                       f.followed_at, f.unfollowed_at
                FROM users u
                LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
            """
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY u.username ASC LIMIT ?"
            params.append(limit)

            async with bot.app_database.acquire() as conn:
                rows = await conn.fetchall(query, tuple(params))

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
        change_stream_title,
        change_stream_category,
        get_stream_info,
        get_follower_stats,
        search_followers,
        get_follower_info,
        get_recent_followers,
        get_recent_unfollowers,
        get_user_info,
        get_user_chat_history,
        get_chat_stats,
        list_users,
    ]
