from __future__ import annotations

import asyncio
import datetime
import logging
import math
from typing import TYPE_CHECKING

from bot_tv.agent.tools._helpers import (
    AgentToolFn,
    clamp_limit,
    format_user_details_row,
    format_user_display_name,
    handle_tool_error,
    normalize_iso_timestamp,
    normalize_role_filter,
    normalize_username,
    require_broadcaster_id,
    sanitize_untrusted_text,
)
from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def build_chat_tools(bot: Bot) -> list[AgentToolFn]:
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
        clean_username: str | None = None
        if username is not None and username.strip():
            clean_username, user_err = normalize_username(username)
            if user_err:
                return user_err

        clean_role, role_err = normalize_role_filter(role)
        if role_err:
            return role_err

        if hours_ago is not None and (not math.isfinite(hours_ago) or hours_ago <= 0):
            return "El parámetro 'hours_ago' debe ser un número mayor que 0."

        since_param, since_err = normalize_iso_timestamp(since, "since")
        if since_err:
            return since_err

        until_param, until_err = normalize_iso_timestamp(until, "until")
        if until_err:
            return until_err

        if hours_ago is not None:
            since_param = (
                datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(hours=hours_ago)
            ).isoformat()

        clean_search = search_term.strip() if search_term else None
        if clean_search == "":
            clean_search = None

        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."
            safe_limit = clamp_limit(limit)

            user_details = ""
            if clean_username:
                user_row = await bot.user_repo.get_user_detail_by_name(
                    clean_username, channel_id, cache=bot.ready_user_cache
                )
                if not user_row:
                    return (
                        f"No se encontró al usuario '{clean_username}' "
                        "en la base de datos."
                    )
                user_details = format_user_details_row(user_row)

            rows = await bot.chat_repo.get_messages_with_filters(
                channel_id=channel_id,
                username=clean_username,
                role=clean_role,
                search_term=clean_search,
                since=since_param,
                until=until_param,
                limit=safe_limit,
            )

            if not rows:
                if user_details:
                    return (
                        f"Historial de chat para {user_details}:\n"
                        "No hay mensajes registrados."
                    )
                return (
                    "No se encontraron mensajes registrados en el chat "
                    "con los filtros indicados."
                )

            header = (
                f"Historial de chat para {user_details}:"
                if user_details
                else "Mensajes de chat encontrados:"
            )

            msg_lines: list[str] = []
            for r in reversed(rows):
                name = format_user_display_name(
                    str(r["username"]), r.get("display_name"), r.get("nickname")
                )
                safe_msg = sanitize_untrusted_text(r.get("message"))
                msg_lines.append(
                    f"- [{format_date(r.get('timestamp'))}] {name}: {safe_msg}"
                )

            body = "\n".join(msg_lines)
            return f"{header}\n<untrusted_chat_data>\n{body}\n</untrusted_chat_data>"
        except Exception as exc:
            return handle_tool_error(LOGGER, "Error al obtener mensajes del chat", exc)

    async def get_chat_stats() -> str:
        """Obtiene estadísticas generales del chat, incluyendo total de mensajes,
        usuarios únicos y top chatters.
        """
        try:
            channel_id, ch_err = await require_broadcaster_id(bot)
            if ch_err or channel_id is None:
                return ch_err or "No hay ningún canal configurado en el bot."

            stats_row, top_rows = await asyncio.gather(
                bot.chat_repo.get_chat_stats(channel_id),
                bot.chat_repo.get_top_chatters(channel_id, limit=5),
            )

            if not stats_row or stats_row["total_messages"] == 0:
                return "No hay estadísticas de chat registradas aún."

            total = stats_row["total_messages"]
            users = stats_row["unique_users"]

            lines: list[str] = [
                f"Estadísticas del Chat:\n"
                f"Mensajes totales guardados: {total}\n"
                f"Usuarios únicos activos: {users}\n\n"
                "Top 5 usuarios más activos:"
            ]
            for idx, r in enumerate(top_rows, 1):
                name = format_user_display_name(
                    str(r["username"]), r.get("display_name"), r.get("nickname")
                )
                lines.append(f"{idx}. {name}: {r['msg_count']} mensajes")

            return "\n".join(lines)
        except Exception as exc:
            return handle_tool_error(
                LOGGER, "Error al obtener estadísticas de chat", exc
            )

    return [
        get_chat_messages,
        get_chat_stats,
    ]
