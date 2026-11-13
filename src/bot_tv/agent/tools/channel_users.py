from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_tv.agent.tools._helpers import (
    AgentToolFn,
    clamp_limit,
    format_user_details_row,
    handle_tool_error,
    normalize_non_empty,
    normalize_username,
    require_broadcaster_id,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_channel_user_tools(bot: Bot) -> list[AgentToolFn]:
    """Construye las herramientas relacionadas con la consulta de usuarios y seguidores
    del canal en la base de datos.
    """

    async def get_channel_user_stats() -> str:
        """Obtiene estadísticas generales sobre los seguidores en la base de datos."""
        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            row = await bot.channel_user_repo.get_follower_stats(channel_id)
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
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener estadísticas de seguidores", exc
            )

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
        clean_term, term_err = normalize_non_empty(search_term, "search_term")
        if term_err or clean_term is None:
            return term_err or "El parámetro 'search_term' no puede estar vacío."

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit)
            rows = await bot.channel_user_repo.search_followers(
                channel_id=channel_id,
                search_term=clean_term,
                active_only=active_only,
                limit=safe_limit,
            )

            if not rows:
                suffix = " activos" if active_only else ""
                return (
                    f"No se encontraron seguidores{suffix} "
                    f"con el término '{clean_term}'."
                )

            lines: list[str] = [f"Resultados de búsqueda ({len(rows)} encontrados):"]
            for r in rows:
                lines.append(f"- {format_user_details_row(r)}")
            return "\n".join(lines)
        except Exception as exc:
            return handle_tool_error(LOGGER, "Error al buscar seguidores", exc)

    async def get_channel_user_info(username: str) -> str:
        """Obtiene información detallada de seguimiento y roles de un usuario
        por su nombre de usuario exacto (username).

        Args:
            username: El nombre de usuario de Twitch exacto (ej: 'twitchdev').
        """
        clean_username, user_err = normalize_username(username)
        if user_err or clean_username is None:
            return user_err or "El nombre de usuario no puede estar vacío."

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            row = await bot.user_repo.get_user_detail_by_name(
                clean_username, channel_id, cache=bot.ready_user_cache
            )
            if not row:
                return (
                    f"No se encontró información del usuario "
                    f"'{clean_username}' en la base de datos."
                )

            return format_user_details_row(row)
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener información del seguidor", exc
            )

    async def get_recent_channel_users(limit: int = 5, active_only: bool = True) -> str:
        """Obtiene la lista de los últimos seguidores activos reales del canal.

        Por defecto filtra únicamente a usuarios que son seguidores vigentes/activos
        y excluye a cuentas marcadas como bots o unfollowers.

        Args:
            limit: Cantidad de seguidores a mostrar.
            active_only: Si es True, solo muestra seguidores vigentes/activos
                (por defecto True).
        """
        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit)
            rows = await bot.channel_user_repo.get_recent_followers(
                channel_id=channel_id, limit=safe_limit, active_only=active_only
            )

            suffix = " activos" if active_only else ""
            if not rows:
                return f"No se encontraron seguidores{suffix} en la base de datos."

            lines: list[str] = [f"Últimos {len(rows)} seguidores{suffix}:"]
            for r in rows:
                lines.append(f"- {format_user_details_row(r)}")
            return "\n".join(lines)
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener seguidores recientes", exc
            )

    async def get_recent_channel_unfollowers(limit: int = 5) -> str:
        """Obtiene la lista de los usuarios que han dejado de seguir
        el canal más recientemente.

        Args:
            limit: Cantidad de usuarios a mostrar.
        """
        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit)
            rows = await bot.channel_user_repo.get_recent_unfollowers(
                channel_id=channel_id, limit=safe_limit
            )

            if not rows:
                return (
                    "No hay registros recientes de usuarios que hayan dejado de seguir."
                )

            lines: list[str] = [f"Últimos {len(rows)} usuarios que dejaron de seguir:"]
            for r in rows:
                lines.append(f"- {format_user_details_row(r)}")
            return "\n".join(lines)
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener unfollowers recientes", exc
            )

    return [
        get_channel_user_stats,
        search_channel_users,
        get_channel_user_info,
        get_recent_channel_users,
        get_recent_channel_unfollowers,
    ]
