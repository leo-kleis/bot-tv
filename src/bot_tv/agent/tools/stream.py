from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any, Literal

import twitchio

from bot_tv.actions.stream import action_update_channel_info
from bot_tv.agent.tools._helpers import (
    MAX_VOD_LIMIT,
    AgentToolFn,
    clamp_limit,
    handle_tool_error,
    normalize_non_empty,
    require_broadcaster_id,
)
from bot_tv.utils.formatting import format_date, parse_twitch_duration

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def _get_current_stream_field(
    bot: Bot,
    channel_id: str,
    field: Literal["title", "game_name"],
    default: str,
) -> str:
    """Obtiene el título o categoría actual consultando stream activo o canal."""
    streams = bot.fetch_streams(user_ids=[channel_id])
    async for stream in streams:
        val = getattr(stream, field, None)
        return val if val else default

    channel_info = await bot.fetch_channel(broadcaster_id=channel_id)
    if channel_info:
        val = getattr(channel_info, field, None)
        if val:
            return val
    return default


def build_stream_tools(bot: Bot) -> list[AgentToolFn]:
    """Construye las herramientas relacionadas con la gestión y consulta del stream."""

    async def change_stream_title(new_title: str) -> str:
        """Cambia el título del stream actual del canal.

        Args:
            new_title: El nuevo título para el stream.
        """
        clean_title, title_err = normalize_non_empty(new_title, "new_title")
        if title_err or clean_title is None:
            return title_err or "El parámetro 'new_title' no puede estar vacío."

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."

            old_title = await _get_current_stream_field(
                bot,
                channel_id,
                "title",
                "Desconocido (Stream offline o sin título)",
            )

            res = await action_update_channel_info(bot, title=clean_title)
            if not res.get("ok"):
                err_msg = res.get("error", "Error desconocido")
                return f"Error al cambiar el título: {err_msg}"
            return (
                f"Título cambiado con éxito.\n"
                f"Antes: '{old_title}'\n"
                f"Después: '{clean_title}'"
            )
        except Exception as exc:
            return handle_tool_error(
                LOGGER,
                "Error al cambiar título del stream",
                exc,
                prefix="Error al cambiar el título",
            )

    async def change_stream_category(category_name: str) -> str:
        """Cambia la categoría/juego del stream actual del canal.

        Args:
            category_name: El nombre de la nueva categoría o juego en Twitch.
        """
        clean_category, cat_err = normalize_non_empty(category_name, "category_name")
        if cat_err or clean_category is None:
            return cat_err or "El parámetro 'category_name' no puede estar vacío."

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."

            games = await bot.fetch_games(names=[clean_category])
            if not games:
                return (
                    f"No se pudo encontrar la categoría '{clean_category}' "
                    "en Twitch. Verifica el nombre."
                )

            target_game = games[0]
            game_id = target_game.id
            resolved_name = target_game.name

            old_category = await _get_current_stream_field(
                bot, channel_id, "game_name", "Desconocida"
            )

            res = await action_update_channel_info(bot, category_id=game_id)
            if not res.get("ok"):
                return (
                    f"Error al cambiar la categoría: "
                    f"{res.get('error', 'Error desconocido')}"
                )
            return (
                f"Categoría cambiada con éxito.\n"
                f"Antes: '{old_category}'\n"
                f"Después: '{resolved_name}'"
            )
        except Exception as exc:
            return handle_tool_error(
                LOGGER,
                "Error al cambiar categoría del stream",
                exc,
                prefix="Error al cambiar la categoría",
            )

    async def get_stream_info() -> str:
        """Obtiene información sobre el stream actual del canal.

        Retorna título, categoría y cantidad de espectadores actuales.
        """
        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."

            streams = bot.fetch_streams(user_ids=[channel_id])
            async for stream in streams:
                return (
                    f"El canal está EN VIVO.\n"
                    f"Título: '{stream.title}'\n"
                    f"Categoría: '{stream.game_name}'\n"
                    f"Espectadores: {stream.viewer_count}"
                )

            channel_info = await bot.fetch_channel(broadcaster_id=channel_id)
            if channel_info:
                return (
                    f"El canal está OFFLINE.\n"
                    f"Último título: '{channel_info.title}'\n"
                    f"Última categoría: '{channel_info.game_name}'"
                )
            return "No se pudo obtener la información del canal."
        except Exception as exc:
            return handle_tool_error(
                LOGGER,
                "Error al obtener información de stream",
                exc,
                prefix="Error al consultar información de stream",
            )

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
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit, maximum=MAX_VOD_LIMIT)

            game_id: str | None = None
            clean_game = game_name.strip() if game_name else None
            if clean_game:
                games = await bot.fetch_games(names=[clean_game])
                if not games:
                    return f"No se encontró la categoría '{clean_game}' en Twitch."
                game_id = games[0].id

            # pyrefly: ignore [missing-attribute]
            videos: list[twitchio.Video] = await bot.fetch_videos(
                user_id=channel_id,
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

            recent_videos = videos[:safe_limit]

            video_ranges: list[tuple[twitchio.Video, str, str]] = []
            count_tasks: list[Coroutine[Any, Any, int]] = []
            for video in recent_videos:
                duration_secs = parse_twitch_duration(video.duration)
                duration = datetime.timedelta(seconds=duration_secs)
                start_utc = video.created_at.isoformat()
                end_utc = (video.created_at + duration).isoformat()
                video_ranges.append((video, start_utc, end_utc))
                count_tasks.append(
                    bot.chat_repo.get_message_count_in_range(
                        channel_id, start_utc, end_utc
                    )
                )

            msg_counts = await asyncio.gather(*count_tasks)

            lines: list[str] = [f"Últimos {len(recent_videos)} streams encontrados:"]
            for idx, ((video, start_utc, end_utc), msg_count) in enumerate(
                zip(video_ranges, msg_counts, strict=True), 1
            ):
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
        except Exception as exc:
            return handle_tool_error(
                LOGGER,
                "Error al obtener streams pasados",
                exc,
                prefix="Error al consultar streams pasados",
            )

    return [
        change_stream_title,
        change_stream_category,
        get_stream_info,
        get_history_vod_streams,
    ]
