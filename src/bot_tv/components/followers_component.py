from __future__ import annotations

import logging
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
        self._initial_followers: dict[str, set[str]] = {}

    async def component_load(self) -> None:
        """Al cargar: obtiene y guarda el snapshot inicial de seguidores."""
        async with self.bot.token_database.acquire() as conn:
            rows = await conn.fetchall("SELECT user_id, username FROM tokens")

        for row in rows:
            channel_id = row["user_id"]
            if channel_id == self.bot.bot_id:
                continue

            LOGGER.info("Obteniendo seguidores del canal %s...", row["username"])
            try:
                await self._fetch_and_sync(channel_id)
            except Exception:
                LOGGER.exception("Error al obtener seguidores de %s", row["username"])

    async def component_teardown(self) -> None:
        """Al cerrar: compara seguidores y reporta cambios."""
        async with self.bot.token_database.acquire() as conn:
            rows = await conn.fetchall("SELECT user_id, username FROM tokens")

        for row in rows:
            channel_id = row["user_id"]
            if channel_id == self.bot.bot_id:
                continue

            LOGGER.info("Verificando seguidores de %s al cerrar...", row["username"])
            try:
                await self._fetch_and_sync(channel_id)

                # Obtener estado final de la DB (recién sincronizado)
                final = await get_follower_ids(self.bot.app_database, channel_id)
                initial = self._initial_followers.get(channel_id, set())

                nuevos = final - initial
                perdidos = initial - final

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
                    LOGGER.info("Sin cambios en seguidores de %s", row["username"])

            except Exception:
                LOGGER.exception("Error al verificar seguidores de %s", row["username"])

    async def _fetch_and_sync(self, channel_id: str) -> None:
        """Consulta la API de Twitch y sincroniza seguidores en la DB."""
        # fetch_user usa keyword argument 'id'
        user = await self.bot.fetch_user(id=int(channel_id))
        if not user:
            LOGGER.warning("No se encontró el usuario con ID %s", channel_id)
            return

        # fetch_followers devuelve ChannelFollowers con .followers (async iterator)
        channel_followers = await user.fetch_followers()

        # Preparar datos para la DB: (user_id, username, followed_at)
        # .followers es un HTTPAsyncIterator, se itera con 'async for'
        follower_tuples: list[tuple[str, str, str | None]] = []
        async for follower_event in channel_followers.followers:
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

        await sync_followers(self.bot.app_database, channel_id, follower_tuples)

        # Si es la primera vez, guardar como snapshot inicial
        if channel_id not in self._initial_followers:
            self._initial_followers[channel_id] = {t[0] for t in follower_tuples}
            LOGGER.info("Snapshot inicial: %d seguidores", len(follower_tuples))
