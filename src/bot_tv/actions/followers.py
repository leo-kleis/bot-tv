"""Acciones de sincronización de seguidores."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_tv.actions.models import SyncFollowersResult

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


async def action_sync_followers(bot: Bot) -> list[SyncFollowersResult]:
    """Sincroniza seguidores de todos los canales. Retorna un resultado por canal."""
    from bot_tv.components.followers_component import FollowersComponent

    channels = await bot.get_channels()
    # pyrefly: ignore [missing-attribute]
    component = bot._components.get("FollowersComponent")

    results: list[SyncFollowersResult] = []

    if not isinstance(component, FollowersComponent):
        LOGGER.error("Componente FollowersComponent no encontrado.")
        for channel in channels:
            results.append(
                SyncFollowersResult(
                    channel=channel["username"],
                    ok=False,
                    error="Componente no disponible.",
                )
            )
        return results

    for channel in channels:
        try:
            await component.check_and_sync(channel["user_id"])
            results.append(SyncFollowersResult(channel=channel["username"], ok=True))
        except Exception as e:
            LOGGER.exception(
                "Error al sincronizar seguidores de %s", channel["username"]
            )
            results.append(
                SyncFollowersResult(channel=channel["username"], ok=False, error=str(e))
            )

    return results
