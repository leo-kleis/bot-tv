from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from twitchio.ext import commands

from database.app import (
    get_follower_ids,
    get_unfollowers_data,
    get_users_info,
    sync_followers,
    upsert_user,
)

if TYPE_CHECKING:
    from bot import Bot

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
        """Al conectar completamente: obtiene seguidores y actualiza."""
        channels = await self.bot.get_channels()

        for channel in channels:
            channel_id = channel["user_id"]
            LOGGER.info("Obteniendo seguidores del canal %s...", channel["username"])
            try:
                await self._check_and_sync(channel_id)
            except Exception:
                LOGGER.exception(
                    "Error al obtener seguidores de %s",
                    channel["username"],
                )

    async def component_teardown(self) -> None:
        """Al cerrar: obtiene seguidores, compara con la DB y actualiza."""
        channels = await self.bot.get_channels()

        for channel in channels:
            channel_id = channel["user_id"]
            LOGGER.info(
                "Verificando seguidores de %s al cerrar...",
                channel["username"],
            )
            try:
                await self._check_and_sync(channel_id)
            except Exception:
                LOGGER.exception(
                    "Error al verificar seguidores de %s",
                    channel["username"],
                )

    async def _check_and_sync(self, channel_id: str) -> None:
        """Obtiene seguidores de la API, compara con la DB y reporta cambios."""
        # 1. Obtener seguidores actuales desde la API
        current = await self._fetch_followers(channel_id)
        current_ids = {t[0] for t in current}

        # Dict: id → nombre para los seguidores actuales
        current_names: dict[str, str] = {t[0]: t[1] for t in current}

        # 2. Obtener seguidores previos desde la DB
        previous_ids = await get_follower_ids(self.bot.app_database, channel_id)

        perdidos: set[str] = set()

        # 3. Comparar
        if previous_ids:
            # Ya teniamos datos → comparar
            nuevos = current_ids - previous_ids
            perdidos = previous_ids - current_ids

            if nuevos:
                # Nickname desde la DB; display_name viene de la API (current_names)
                nuevos_info = await get_users_info(self.bot.app_database, list(nuevos))
                now_iso = datetime.now(UTC).isoformat()
                labels = [
                    _format_label(
                        uid,
                        current_names.get(uid, uid),
                        now_iso,
                        nuevos_info.get(uid, {}).get("nickname"),
                    )
                    for uid in nuevos
                ]
                LOGGER.info(
                    "[+] Nuevos seguidores (%d): %s",
                    len(nuevos),
                    ", ".join(labels),
                )
            if perdidos:
                # display_name, nickname y followed_at vienen de la DB
                # (aún no se ha llamado a sync_followers, así que los datos siguen ahí)
                perdidos_data = await get_unfollowers_data(
                    self.bot.app_database, channel_id, list(perdidos)
                )
                labels = [
                    _format_label(
                        uid,
                        perdidos_data.get(uid, {}).get("display_name") or uid,
                        perdidos_data.get(uid, {}).get("followed_at"),
                        perdidos_data.get(uid, {}).get("nickname"),
                    )
                    for uid in perdidos
                ]
                LOGGER.warning(
                    "[-] Dejaron de seguir (%d): %s",
                    len(perdidos),
                    ", ".join(labels),
                )
            if not nuevos and not perdidos:
                LOGGER.info("Sin cambios en seguidores (%d total)", len(current_ids))
        else:
            # Primera vez → solo informar
            LOGGER.info("Primera carga: %d seguidores registrados", len(current_ids))

        # 4. Actualizar la DB con los datos actuales (siempre DESPUÉS del log)
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
            fid = str(follower_event.user.id)
            fname = follower_event.user.name or str(follower_event.user.id)
            followed_at = (
                follower_event.followed_at.isoformat()
                if follower_event.followed_at
                else None
            )
            follower_tuples.append((fid, fname, followed_at))

            # Registrar como usuario en la tabla users
            await upsert_user(self.bot.app_database, fid, fname, fname)

            # Progreso en tiempo real
            sys.stdout.write(f"\r  Obteniendo seguidores... {count}/{total}")
            sys.stdout.flush()

        # Limpiar la línea de progreso
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()

        return follower_tuples
