"""Acciones para búsqueda de categorías y actualización de información del stream."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import twitchio

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def action_search_categories(bot: Bot, query: str) -> list[dict[str, str]]:
    """Busca categorías/juegos en Twitch por nombre."""
    clean_query = query.strip()
    if not clean_query:
        return []

    try:
        categories = await bot.search_categories(query=clean_query)
        results: list[dict[str, str]] = []
        for cat in categories:
            results.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "box_art_url": getattr(cat, "box_art_url", "") or "",
                }
            )
        return results
    except Exception as e:
        LOGGER.error(
            "Error al buscar categorías en Twitch con query '%s': %s",
            clean_query,
            e,
        )
        return []


async def action_update_channel_info(
    bot: Bot,
    title: str | None = None,
    category_id: str | None = None,
) -> dict[str, Any]:
    """Actualiza el título y/o la categoría del canal en Twitch."""
    channels = await bot.get_channels()
    if not channels:
        return {"ok": False, "error": "No hay canales configurados para el bot."}

    channel_id = channels[0]["user_id"]

    try:
        clean_title = title.strip() if title is not None and title.strip() else None
        clean_category_id = (
            category_id.strip()
            if category_id is not None and category_id.strip()
            else None
        )

        if clean_title is None and clean_category_id is None:
            return {
                "ok": False,
                "error": "No se especificaron cambios de título o categoría.",
            }

        partial = twitchio.PartialUser(id=channel_id, http=bot._http)
        await partial.modify_channel(
            title=clean_title,
            game_id=clean_category_id,
        )
        LOGGER.info(
            "Información del canal %s actualizada en Twitch: title=%s, game_id=%s",
            channel_id,
            clean_title,
            clean_category_id,
        )
        return {"ok": True}
    except twitchio.HTTPException as e:
        LOGGER.error("Fallo al actualizar canal en Twitch (HTTP %s): %s", e.status, e)
        return {"ok": False, "error": f"Error de Twitch (HTTP {e.status}): {e}"}
    except Exception as e:
        LOGGER.exception("Error inesperado al actualizar canal en Twitch: %s", e)
        return {"ok": False, "error": f"Error inesperado: {e}"}
