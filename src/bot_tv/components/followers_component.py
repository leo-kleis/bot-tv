from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from twitchio.ext import commands

from bot_tv.app_database import (
    get_follower_ids,
    sync_followers,
    upsert_user,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class FollowersComponent(commands.Component):
    """Componente que rastrea seguidores del canal entre sesiones."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def component_load(self) -> None:
        """Al cargar: obtiene seguidores, compara con la DB y actualiza."""
        async with self.bot.token_database.acquire() as conn:
            rows = await conn.fetchall("SELECT user_id, username FROM tokens")

        for row in rows:
            channel_id = row["user_id"]
            if channel_id == self.bot.bot_id:
                continue

            LOGGER.info("Obteniendo seguidores del canal %s...", row["username"])
            try:
                await self._check_and_sync(channel_id)
            except Exception:
                LOGGER.exception("Error al obtener seguidores de %s", row["username"])

    async def component_teardown(self) -> None:
        """Al cerrar: obtiene seguidores, compara con la DB y actualiza."""
        async with self.bot.token_database.acquire() as conn:
            rows = await conn.fetchall("SELECT user_id, username FROM tokens")

        for row in rows:
            channel_id = row["user_id"]
            if channel_id == self.bot.bot_id:
                continue

            LOGGER.info("Verificando seguidores de %s al cerrar...", row["username"])
            try:
                await self._check_and_sync(channel_id)
            except Exception:
                LOGGER.exception("Error al verificar seguidores de %s", row["username"])

    async def _check_and_sync(self, channel_id: str) -> None:
        """Obtiene seguidores de la API, compara con la DB y reporta cambios."""
        # 1. Obtener seguidores actuales desde la API
        current = await self._fetch_followers(channel_id)
        current_ids = {t[0] for t in current}

        # 2. Obtener seguidores previos desde la DB
        previous_ids = await get_follower_ids(self.bot.app_database, channel_id)

        # 3. Comparar
        if previous_ids:
            # Ya teniamos datos → comparar
            nuevos = current_ids - previous_ids
            perdidos = previous_ids - current_ids

            if nuevos:
                LOGGER.info(
                    "[+] Nuevos seguidores (%d): %s",
                    len(nuevos),
                    ", ".join(nuevos),
                )
            if perdidos:
                LOGGER.warning(
                    "[-] Dejaron de seguir (%d): %s",
                    len(perdidos),
                    ", ".join(perdidos),
                )
            if not nuevos and not perdidos:
                LOGGER.info("Sin cambios en seguidores (%d total)", len(current_ids))
        else:
            # Primera vez → solo informar
            LOGGER.info("Primera carga: %d seguidores registrados", len(current_ids))

        # 4. Actualizar la DB con los datos actuales
        await sync_followers(self.bot.app_database, channel_id, current)

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
