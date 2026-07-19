from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from twitchio.ext import commands

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

    Ejemplo: [194638791] NombreUsuario (08/03/26) - apodo
    """
    if followed_at_iso:
        try:
            dt = datetime.fromisoformat(followed_at_iso)
            date_str = f" ({dt.strftime('%d/%m/%y')})"
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
        self._is_syncing = False

    @commands.Component.listener()
    async def event_bot_fully_connected(self) -> None:
        """Sincroniza seguidores al iniciar."""
        channels = await self.bot.get_channels()
        for channel in channels:
            await self.check_and_sync(channel["user_id"])

    async def check_and_sync(self, channel_id: str) -> None:
        """Compara seguidores de la API con la DB y sincroniza diferencias."""
        if self._is_syncing:
            raise RuntimeError("Ya hay una sincronización de seguidores en curso.")

        self._is_syncing = True
        try:
            # Notificar progreso inicial para bloquear el botón globalmente
            await self.bot.event_bus.emit(
                FollowerProgressEvent(
                    timestamp=datetime.now().isoformat(),
                    count=0,
                    total=0,
                )
            )

            # 1. Recolectar seguidores actuales de la API (sin tocar la DB)
            current = await self._fetch_followers(channel_id)
            current_map: dict[str, tuple[str, str | None]] = {
                uid: (uname, fat) for uid, uname, fat in current
            }
            current_ids = set(current_map.keys())

            # 2. Obtener IDs previos de la DB (ya están en cache)
            previous_ids = await self.bot.channel_user_repo.get_follower_ids(channel_id)

            # 3. Comparar localmente
            nuevos_ids = current_ids - previous_ids
            perdidos_ids = previous_ids - current_ids
            is_first_sync = not previous_ids

            # 4. Preparar labels para el evento (UI)
            new_labels: list[str] = []
            lost_labels: list[str] = []

            if previous_ids:
                if nuevos_ids:
                    nuevos_info = await self.bot.user_repo.get_users_info(
                        list(nuevos_ids)
                    )
                    now_iso = datetime.now(UTC).isoformat()
                    nuevos_ordenados = sorted(
                        nuevos_ids,
                        key=lambda uid: current_map[uid][0].lower(),
                    )
                    new_labels = [
                        _format_label(
                            uid,
                            current_map[uid][0],
                            now_iso,
                            nuevos_info.get(uid, {}).get("nickname"),
                        )
                        for uid in nuevos_ordenados
                    ]

                if perdidos_ids:
                    perdidos_data = await self.bot.user_repo.get_unfollowers_data(
                        channel_id, list(perdidos_ids)
                    )
                    perdidos_ordenados = sorted(
                        perdidos_ids,
                        key=lambda uid: (
                            perdidos_data.get(uid, {}).get("display_name") or uid
                        ).lower(),
                    )
                    lost_labels = [
                        _format_label(
                            uid,
                            perdidos_data.get(uid, {}).get("display_name") or uid,
                            perdidos_data.get(uid, {}).get("followed_at"),
                            perdidos_data.get(uid, {}).get("nickname"),
                        )
                        for uid in perdidos_ordenados
                    ]

            # 5. Emitir evento de sync (UI)
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

            # 6. Escribir solo las diferencias a la DB (batch)
            new_followers = [
                (uid, current_map[uid][0], current_map[uid][1])
                for uid in (current_ids if is_first_sync else nuevos_ids)
            ]
            await self.bot.channel_user_repo.sync_followers(
                channel_id,
                new_followers,
                unfollowed_ids=list(perdidos_ids),
            )
        finally:
            self._is_syncing = False

    async def _fetch_followers(
        self, channel_id: str
    ) -> list[tuple[str, str, str | None]]:
        """Consulta la API de Twitch y devuelve la lista de seguidores.

        Solo recolecta datos, NO toca la base de datos.
        """
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

            # Emitir progreso en tiempo real (sin tocar DB)
            await self.bot.event_bus.emit(
                FollowerProgressEvent(
                    timestamp=datetime.now().isoformat(),
                    count=count,
                    total=total,
                )
            )

        return follower_tuples
