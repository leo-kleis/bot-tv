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

    async def get_last_follower(active_only: bool = False) -> str:
        """Obtiene el último seguidor registrado en la base de datos local.

        Args:
            active_only: Si es True, solo busca seguidores vigentes.
        """
        try:
            # Armar la query
            query = """
                SELECT f.user_id, f.followed_at, f.unfollowed_at, 
                       u.username, u.display_name, u.nickname
                FROM followers f
                JOIN users u ON f.user_id = u.user_id
                WHERE f.channel_id = ?
            """
            if active_only:
                query += " AND f.unfollowed_at IS NULL"
            query += " ORDER BY f.followed_at DESC LIMIT 1"

            async with bot.app_database.acquire() as conn:
                row = await conn.fetchone(query, (OWNER_ID,))

            if not row:
                suffix = " vigente" if active_only else ""
                return (
                    f"No se encontró ningún seguidor{suffix} "
                    f"registrado en la base de datos."
                )

            nickname = row["nickname"]
            display_name = row["display_name"] or row["username"]
            name_str = f"{display_name} ({nickname})" if nickname else display_name

            followed_str = format_date(row["followed_at"])

            if row["unfollowed_at"]:
                unfollowed_str = format_date(row["unfollowed_at"])
                return (
                    f"El último seguidor fue {name_str}.\n"
                    f"Siguió el: {followed_str}\n"
                    f"Dejó de seguir el: {unfollowed_str} (No vigente)"
                )
            else:
                active_suffix = " vigente" if active_only else ""
                return (
                    f"El último seguidor{active_suffix} es {name_str}.\n"
                    f"Siguió el: {followed_str}"
                )
        except Exception as e:
            LOGGER.error("Error al buscar último seguidor en base de datos: %s", e)
            return f"Error al consultar base de datos: {e}"

    return [
        change_stream_title,
        change_stream_category,
        get_stream_info,
        get_last_follower,
    ]
