from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from twitchio.ext import commands

from bot_tv.database.app import (
    get_follower_ids,
    get_unfollowers_data,
    get_users_info,
    sync_followers,
    upsert_user,
)
from bot_tv.events import FollowerProgressEvent, FollowerSyncEvent

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def _format_label(
    uid: str,
    display_name: str,
    followed_at_iso: str | None,
    nickname: str | None,
) -> str:
    """Formatea una entrada de seguidor para el log.

    Ejemplo: [194638791] NombreUsuario (08-03-26) - apodo
    """
    if followed_at_iso:
        try:
            dt = datetime.fromisoformat(followed_at_iso)
            date_str = f" ({dt.strftime('%d-%m-%y')})"
        except ValueError:
            date_str = ""
    else:
        date_str = ""
    nick_str = f" - {nickname}" if nickname else ""
    return f"[{uid}] {display_name}{date_str}{nick_str}"


class FollowersComponent(commands.Component):
    """Componente que rastrea seguidores del canal entre sesiones."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Component.listener()
    async def event_bot_fully_connected(self) -> None:
        """Sincroniza seguidores al iniciar."""
        channels = await self.bot.get_channels()
        for channel in channels:
            await self.check_and_sync(channel["user_id"])

    async def check_and_sync(self, channel_id: str) -> None:
        """Obtiene seguidores de la API, compara con la DB y emite FollowerSyncEvent."""
        current = await self._fetch_followers(channel_id)
        current_ids = {t[0] for t in current}
        current_names: dict[str, str] = {t[0]: t[1] for t in current}

        previous_ids = await get_follower_ids(self.bot.app_database, channel_id)

        perdidos: set[str] = set()
        new_labels: list[str] = []
        lost_labels: list[str] = []
        is_first_sync = not previous_ids

        if previous_ids:
            nuevos = current_ids - previous_ids
            perdidos = previous_ids - current_ids

            if nuevos:
                nuevos_info = await get_users_info(self.bot.app_database, list(nuevos))
                now_iso = datetime.now(UTC).isoformat()
                new_labels = [
                    _format_label(
                        uid,
                        current_names.get(uid, uid),
                        now_iso,
                        nuevos_info.get(uid, {}).get("nickname"),
                    )
                    for uid in nuevos
                ]

            if perdidos:
                perdidos_data = await get_unfollowers_data(
                    self.bot.app_database, channel_id, list(perdidos)
                )
                lost_labels = [
                    _format_label(
                        uid,
                        perdidos_data.get(uid, {}).get("display_name") or uid,
                        perdidos_data.get(uid, {}).get("followed_at"),
                        perdidos_data.get(uid, {}).get("nickname"),
                    )
                    for uid in perdidos
                ]

        await self.bot.event_bus.emit(
            FollowerSyncEvent(
                timestamp=datetime.now().isoformat(),
                new_count=len(new_labels),
                lost_count=len(lost_labels),
                total=len(current_ids),
                new_labels=new_labels,
                lost_labels=lost_labels,
                is_first_sync=is_first_sync,
            )
        )

        await sync_followers(
            self.bot.app_database, channel_id, current, unfollowed_ids=list(perdidos)
        )

    async def _fetch_followers(
        self, channel_id: str
    ) -> list[tuple[str, str, str | None]]:
        """Consulta la API de Twitch y devuelve la lista de seguidores."""
        user = await self.bot.fetch_user(id=int(channel_id))
        if not user:
            LOGGER.warning("No se encontró el usuario con ID %s", channel_id)
            return []

        channel_followers = await user.fetch_followers()
        total = channel_followers.total

        follower_tuples: list[tuple[str, str, str | None]] = []
        count = 0
        async for follower_event in channel_followers.followers:
            count += 1
            fid = follower_event.user.id
            fname = follower_event.user.name or follower_event.user.id
            followed_at = (
                follower_event.followed_at.isoformat()
                if follower_event.followed_at
                else None
            )
            follower_tuples.append((fid, fname, followed_at))

            await upsert_user(self.bot.app_database, fid, fname, fname)

            # Emitir progreso en tiempo real
            await self.bot.event_bus.emit(
                FollowerProgressEvent(
                    timestamp=datetime.now().isoformat(),
                    count=count,
                    total=total,
                )
            )

        return follower_tuples
