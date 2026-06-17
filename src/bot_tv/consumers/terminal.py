"""TerminalConsumer: reproduce el output Rich original del bot en la terminal.

Se suscribe al EventBus y formatea cada evento exactamente como lo hacían
los componentes antes de la refactorización, manteniendo el comportamiento
actual de `bot-tv` intacto.
"""

from __future__ import annotations

import logging

from bot_tv.event_bus import EventBus
from bot_tv.events import (
    ChatMessageEvent,
    ClipCreatedEvent,
    FollowerProgressEvent,
    FollowerSyncEvent,
    StreamOfflineEvent,
    StreamOnlineEvent,
    UserJoinEvent,
    UserPartEvent,
    ViewerUpdateEvent,
)
from bot_tv.utils.colors import (
    BOLD,
    CONSOLE,
    CYAN,
    DIM,
    MORADO,
    RESET,
    ROJO,
    VERDE,
    format_colored_name,
    format_timestamp,
)

LOGGER = logging.getLogger(__name__)


class TerminalConsumer:
    """Consume eventos del EventBus y los muestra en la terminal con Rich.

    Reproduce exactamente el output que tenían los componentes antes
    de la refactorización. Solo se instancia cuando se usa `bot-tv`.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._register()

    def _register(self) -> None:
        self._event_bus.subscribe(ChatMessageEvent, self._on_chat_message)
        self._event_bus.subscribe(UserJoinEvent, self._on_user_join)
        self._event_bus.subscribe(UserPartEvent, self._on_user_part)
        self._event_bus.subscribe(StreamOnlineEvent, self._on_stream_online)
        self._event_bus.subscribe(StreamOfflineEvent, self._on_stream_offline)
        self._event_bus.subscribe(ViewerUpdateEvent, self._on_viewer_update)
        self._event_bus.subscribe(FollowerSyncEvent, self._on_follower_sync)
        self._event_bus.subscribe(FollowerProgressEvent, self._on_follower_progress)
        self._event_bus.subscribe(ClipCreatedEvent, self._on_clip_created)

    # ── Chat ────────────────────────────────────────────────────────────────

    async def _on_chat_message(self, event: ChatMessageEvent) -> None:
        nombre = format_colored_name(
            event.display_name, event.nickname, *event.color_rgb
        )
        role_dim = f"{DIM}({event.role}){RESET}"
        timestamp = format_timestamp()
        CONSOLE.print(f"{timestamp} {nombre} {role_dim}: {event.text}")

    # ── IRC ─────────────────────────────────────────────────────────────────

    async def _on_user_join(self, event: UserJoinEvent) -> None:
        nombre = format_colored_name(
            event.display_name, event.nickname, *event.color_rgb
        )
        role_dim = f"{DIM}({event.role}){RESET}"
        timestamp = format_timestamp()
        accion = f"{VERDE}JOIN{RESET}"
        CONSOLE.print(f"{timestamp} {nombre} {role_dim}: {accion}")

    async def _on_user_part(self, event: UserPartEvent) -> None:
        nombre = format_colored_name(
            event.display_name, event.nickname, *event.color_rgb
        )
        role_dim = f"{DIM}({event.role}){RESET}"
        timestamp = format_timestamp()
        accion = f"{ROJO}PART{RESET}"
        CONSOLE.print(f"{timestamp} {nombre} {role_dim}: {accion}")

    # ── Stream ───────────────────────────────────────────────────────────────

    async def _on_stream_online(self, event: StreamOnlineEvent) -> None:
        timestamp = format_timestamp()
        info_parts = []
        if event.title:
            info_parts.append(f'"{event.title}"')
        if event.category:
            info_parts.append(f"({event.category})")
        info_str = f"  {' '.join(info_parts)}" if info_parts else ""

        CONSOLE.print(
            f"{timestamp} {VERDE}{BOLD}STREAM ONLINE{RESET}  "
            f"{MORADO}►{RESET} {event.broadcaster_name} en vivo{info_str}"
        )

    async def _on_stream_offline(self, event: StreamOfflineEvent) -> None:
        timestamp = format_timestamp()
        nombre = event.broadcaster_name or "Canal"
        CONSOLE.print(
            f"{timestamp} {ROJO}{BOLD}STREAM OFFLINE{RESET}  "
            f"{MORADO}►{RESET} {nombre} terminó su stream"
        )

    async def _on_viewer_update(self, event: ViewerUpdateEvent) -> None:
        timestamp = format_timestamp()
        diferencia = ""
        if event.diff is not None:
            if event.diff > 0:
                diferencia = f" {VERDE}(+{event.diff}){RESET}"
            elif event.diff < 0:
                diferencia = f" {ROJO}({event.diff}){RESET}"

        CONSOLE.print(
            f"{timestamp} {CYAN}VIEWERS{RESET}         "
            f"{MORADO}►{RESET} {event.count} espectadores{diferencia}"
        )

    # ── Seguidores ───────────────────────────────────────────────────────────

    async def _on_follower_sync(self, event: FollowerSyncEvent) -> None:
        if event.is_first_sync:
            LOGGER.info("Primera carga: %d seguidores registrados", event.total)
            return

        if event.new_count:
            LOGGER.info(
                "[+] Nuevos seguidores (%d): %s",
                event.new_count,
                ", ".join(event.new_labels),
            )
        if event.lost_count:
            LOGGER.warning(
                "[-] Dejaron de seguir (%d): %s",
                event.lost_count,
                ", ".join(event.lost_labels),
            )
        if not event.new_count and not event.lost_count:
            LOGGER.info("Sin cambios en seguidores (%d total)", event.total)

    async def _on_follower_progress(self, event: FollowerProgressEvent) -> None:
        # Progreso en tiempo real (línea que se sobreescribe)
        import sys

        if event.count < event.total:
            sys.stdout.write(
                f"\r  Obteniendo seguidores... {event.count}/{event.total}"
            )
            sys.stdout.flush()
        else:
            # Limpiar la línea al terminar
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()

    # ── Clips ────────────────────────────────────────────────────────────────

    async def _on_clip_created(self, event: ClipCreatedEvent) -> None:
        LOGGER.info("%s¡Clip creado con éxito!%s URL: %s", VERDE, RESET, event.url)
