from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.utils.env import OWNER_ID

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_stream_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye las herramientas relacionadas con la gestión y consulta del stream."""

    async def change_stream_title(new_title: str) -> str:
        """Cambia el título del stream actual del canal.

        Args:
            new_title: El nuevo título para el stream.
        """
        try:
            old_title = "Desconocido (Stream offline o sin título)"
            streams = bot.fetch_streams(user_ids=[int(OWNER_ID)])
            async for stream in streams:
                if stream.title:
                    old_title = stream.title
                break
            else:
                channel_info = await bot.fetch_channel(broadcaster_id=OWNER_ID)
                if channel_info and channel_info.title:
                    old_title = channel_info.title

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
            games = await bot.fetch_games(names=[category_name])
            if not games:
                return (
                    f"No se pudo encontrar la categoría '{category_name}' "
                    f"en Twitch. Verifica el nombre."
                )

            target_game = games[0]
            game_id = target_game.id
            resolved_name = target_game.name

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

    return [
        change_stream_title,
        change_stream_category,
        get_stream_info,
    ]
