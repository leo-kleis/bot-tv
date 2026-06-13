from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from utils.colors import (
    BOLD,
    CYAN,
    DIM,
    MORADO,
    RESET,
    ROJO,
    VERDE,
    format_timestamp,
)

if TYPE_CHECKING:
    from bot import Bot

LOGGER = logging.getLogger(__name__)

# Intervalo de polling para viewers (en segundos)
VIEWER_POLL_INTERVAL = 60


class StreamComponent(commands.Component):
    """Componente que monitorea el estado del stream y muestra viewers.

    Funcionalidad:
    - Detecta stream online/offline via EventSub (instantáneo)
    - Muestra viewer count en terminal, solo cuando cambia (polling cada 60s)
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._viewer_task: asyncio.Task[None] | None = None
        self._last_viewer_count: int | None = None
        self._stream_online: bool = False
        self._channel_ids: list[str] = []

    # ── Ciclo de vida ───────────────────────────────────────────────

    @commands.Component.listener()
    async def event_bot_fully_connected(self) -> None:
        """Inicia el monitoreo cuando el bot está completamente conectado."""
        # Obtener los canales configurados (excluyendo al bot)
        channels = await self.bot.get_channels()

        self._channel_ids = [channel["user_id"] for channel in channels]

        if not self._channel_ids:
            LOGGER.warning("StreamComponent: no hay canales para monitorear.")
            return

        # Verificar estado inicial del stream
        await self._check_initial_status()

        # Iniciar polling de viewers
        self._viewer_task = asyncio.create_task(self._viewer_poll_loop())

    async def component_teardown(self) -> None:
        """Detiene el polling al cerrar el componente."""
        if self._viewer_task and not self._viewer_task.done():
            self._viewer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._viewer_task

    # ── EventSub: Stream Online/Offline ─────────────────────────────

    @commands.Component.listener()
    async def event_eventsub_notification_stream_start(
        self, payload: twitchio.StreamOnline
    ) -> None:
        """Se ejecuta cuando un stream se pone online (EventSub)."""
        self._stream_online = True
        self._last_viewer_count = None  # Resetear para forzar primer print

        timestamp = format_timestamp()

        # Obtener info del stream para título y categoría
        titulo = ""
        categoria = ""
        try:
            streams = self.bot.fetch_streams(user_ids=[int(payload.broadcaster.id)])
            async for stream in streams:
                titulo = stream.title or ""
                categoria = stream.game_name or ""
                break
        except Exception:
            pass

        nombre = payload.broadcaster.display_name or payload.broadcaster.name
        info_parts = []
        if titulo:
            info_parts.append(f'"{titulo}"')
        if categoria:
            info_parts.append(f"({categoria})")
        info_str = f"  {' '.join(info_parts)}" if info_parts else ""

        print(
            f"{timestamp} {VERDE}{BOLD}STREAM ONLINE{RESET}  "
            f"{MORADO}►{RESET} {nombre} inició stream{info_str}"
        )

    @commands.Component.listener()
    async def event_eventsub_notification_stream_end(
        self, payload: twitchio.StreamOffline
    ) -> None:
        """Se ejecuta cuando un stream se pone offline (EventSub)."""
        self._stream_online = False
        self._last_viewer_count = None

        timestamp = format_timestamp()

        nombre = payload.broadcaster.display_name or payload.broadcaster.name

        print(
            f"{timestamp} {ROJO}{BOLD}STREAM OFFLINE{RESET}  "
            f"{MORADO}►{RESET} {nombre} terminó su stream"
        )

    # ── Polling de viewers ──────────────────────────────────────────

    async def _check_initial_status(self) -> None:
        """Verifica el estado del stream al iniciar el componente."""
        for channel_id in self._channel_ids:
            try:
                streams = self.bot.fetch_streams(user_ids=[int(channel_id)])
                async for stream in streams:
                    self._stream_online = True
                    viewer_count = stream.viewer_count
                    self._last_viewer_count = viewer_count

                    timestamp = format_timestamp()

                    nombre = stream.user.display_name or stream.user.name
                    titulo = stream.title or ""
                    categoria = stream.game_name or ""

                    info_parts = []
                    if titulo:
                        info_parts.append(f'"{titulo}"')
                    if categoria:
                        info_parts.append(f"({categoria})")
                    info_str = f"  {' '.join(info_parts)}" if info_parts else ""

                    print(
                        f"{timestamp} {VERDE}{BOLD}STREAM ONLINE{RESET}  "
                        f"{MORADO}►{RESET} {nombre} en vivo{info_str}"
                    )
                    print(
                        f"{timestamp} {CYAN}VIEWERS{RESET}         "
                        f"{MORADO}►{RESET} {viewer_count} espectadores"
                    )
                    break
                else:
                    # El stream no está en vivo
                    timestamp = format_timestamp()
                    print(
                        f"{timestamp} {ROJO}{BOLD}STREAM OFFLINE{RESET}  "
                        f"{MORADO}►{RESET} {DIM}Canal no está en vivo{RESET}"
                    )
            except Exception as e:
                LOGGER.error("Error al verificar estado inicial del stream: %s", e)

    async def _viewer_poll_loop(self) -> None:
        """Loop que consulta el conteo de viewers cada VIEWER_POLL_INTERVAL segundos.

        Solo imprime cuando el valor cambia respecto al último conocido.
        """
        while True:
            await asyncio.sleep(VIEWER_POLL_INTERVAL)

            if not self._stream_online:
                continue

            for channel_id in self._channel_ids:
                try:
                    streams = self.bot.fetch_streams(user_ids=[int(channel_id)])
                    found = False
                    async for stream in streams:
                        found = True
                        viewer_count = stream.viewer_count

                        # Solo imprimir si cambió
                        if viewer_count != self._last_viewer_count:
                            diferencia = ""
                            if self._last_viewer_count is not None:
                                diff = viewer_count - self._last_viewer_count
                                if diff > 0:
                                    diferencia = f" {VERDE}(+{diff}){RESET}"
                                elif diff < 0:
                                    diferencia = f" {ROJO}({diff}){RESET}"

                            self._last_viewer_count = viewer_count

                            timestamp = format_timestamp()
                            print(
                                f"{timestamp} {CYAN}VIEWERS{RESET}         "
                                f"{MORADO}►{RESET} "
                                f"{viewer_count} espectadores{diferencia}"
                            )
                        break

                    # Si no se encontró stream, se apagó entre polls
                    if not found and self._stream_online:
                        self._stream_online = False
                        self._last_viewer_count = None
                except Exception as e:
                    LOGGER.error("Error al consultar viewers: %s", e)
