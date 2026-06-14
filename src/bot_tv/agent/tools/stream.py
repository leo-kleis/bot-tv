from __future__ import annotations

import datetime
import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from bot_tv.utils.env import OWNER_ID
from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def parse_duration(duration_str: str) -> datetime.timedelta:
    """Parsea una duración en formato Twitch (ej: "1h30m12s") a timedelta."""
    hours = 0
    minutes = 0
    seconds = 0

    h_match = re.search(r"(\d+)h", duration_str)
    m_match = re.search(r"(\d+)m", duration_str)
    s_match = re.search(r"(\d+)s", duration_str)

    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    if s_match:
        seconds = int(s_match.group(1))

    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


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

    async def get_history_vod_streams(
        game_name: str | None = None,
        period: Literal["all", "day", "week", "month"] = "all",
        sort: Literal["time", "trending", "views"] = "time",
        limit: int = 5,
    ) -> str:
        """Obtiene un historial de los streams (directos) pasados del canal a través
        de los VODs guardados en Twitch, detallando su fecha, duración y total
        de mensajes.

        Args:
            game_name: Filtrar streams que pertenezcan a este juego o categoría
                (opcional).
            period: El período para buscar streams.
                Valores válidos: 'all', 'day', 'week', 'month' (por defecto: 'all').
            sort: El orden para los streams.
                Valores válidos: 'time' (por fecha), 'trending', 'views'
                (por reproducciones) (por defecto: 'time').
            limit: Cantidad de streams pasados a retornar.
        """
        try:
            limit = max(1, limit)

            game_id = None
            if game_name:
                games = await bot.fetch_games(names=[game_name])
                if not games:
                    return f"No se encontró la categoría '{game_name}' en Twitch."
                game_id = games[0].id

            # pyrefly: ignore [missing-attribute]
            videos = await bot.fetch_videos(
                user_id=OWNER_ID,
                type="archive",
                period=period,
                sort=sort,
                game_id=game_id,
            )
            if not videos:
                return (
                    "No se encontraron streams pasados (VODs) en Twitch "
                    "con los filtros indicados."
                )

            recent_videos = videos[:limit]

            lines = [f"Últimos {len(recent_videos)} streams encontrados:"]
            for idx, video in enumerate(recent_videos, 1):
                duration = parse_duration(video.duration)

                # Buscar cantidad de mensajes en ese rango de tiempo (UTC)
                start_utc = video.created_at.isoformat()
                end_utc = (video.created_at + duration).isoformat()

                count_query = """
                    SELECT COUNT(*) as msg_count
                    FROM chat_history
                    WHERE channel_id = ? AND timestamp >= ? AND timestamp <= ?
                """
                async with bot.app_database.acquire() as conn:
                    row = await conn.fetchone(
                        count_query, (OWNER_ID, start_utc, end_utc)
                    )

                msg_count = row["msg_count"] if row else 0

                start_local = format_date(start_utc)
                end_local = format_date(end_utc)

                lines.append(
                    f"{idx}. Título: '{video.title}'\n"
                    f"   Inicio: {start_local} (Local)\n"
                    f"   Fin: {end_local} (Local)\n"
                    f"   Duración: {video.duration}\n"
                    f"   Mensajes en chat: {msg_count}\n"
                    f"   VOD: {video.url}"
                )

            return "\n\n".join(lines)
        except Exception as e:
            LOGGER.error("Error al obtener streams pasados: %s", e)
            return f"Error al consultar streams pasados: {e}"

    return [
        change_stream_title,
        change_stream_category,
        get_stream_info,
        get_history_vod_streams,
    ]
