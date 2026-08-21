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
    TwitchBanEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchCheerEvent,
    TwitchFollowEvent,
    TwitchMessageDeleteEvent,
    TwitchPredictionBeginEvent,
    TwitchPredictionEndEvent,
    TwitchPredictionLockEvent,
    TwitchPredictionProgressEvent,
    TwitchRaidEvent,
    TwitchSubscribeEvent,
    TwitchSubscriptionGiftEvent,
    TwitchSubscriptionMessageEvent,
    TwitchUnbanEvent,
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
    NARANJA,
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

        # Twitch EventSub Alerts
        self._event_bus.subscribe(TwitchFollowEvent, self._on_twitch_follow)
        self._event_bus.subscribe(TwitchRaidEvent, self._on_twitch_raid)
        self._event_bus.subscribe(TwitchSubscribeEvent, self._on_twitch_subscribe)
        self._event_bus.subscribe(TwitchSubscriptionGiftEvent, self._on_twitch_sub_gift)
        self._event_bus.subscribe(
            TwitchSubscriptionMessageEvent, self._on_twitch_sub_message
        )
        self._event_bus.subscribe(TwitchCheerEvent, self._on_twitch_cheer)
        self._event_bus.subscribe(
            TwitchChannelPointsRedeemEvent, self._on_twitch_points_redeem
        )
        self._event_bus.subscribe(TwitchPredictionBeginEvent, self._on_prediction_begin)
        self._event_bus.subscribe(
            TwitchPredictionProgressEvent, self._on_prediction_progress
        )
        self._event_bus.subscribe(TwitchPredictionLockEvent, self._on_prediction_lock)
        self._event_bus.subscribe(TwitchPredictionEndEvent, self._on_prediction_end)
        self._event_bus.subscribe(TwitchBanEvent, self._on_twitch_ban)
        self._event_bus.subscribe(TwitchUnbanEvent, self._on_twitch_unban)
        self._event_bus.subscribe(TwitchChatClearEvent, self._on_twitch_chat_clear)
        self._event_bus.subscribe(
            TwitchChatClearUserEvent, self._on_twitch_chat_clear_user
        )
        self._event_bus.subscribe(
            TwitchMessageDeleteEvent, self._on_twitch_message_delete
        )

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
        timestamp = format_timestamp()

        if event.is_first_sync:
            CONSOLE.print(
                f"{timestamp} {NARANJA}FOLLOWERS{RESET}      "
                f"{MORADO}►{RESET} Primera carga: {event.total} seguidores registrados"
            )
            return

        if not event.new_count and not event.lost_count:
            CONSOLE.print(
                f"{timestamp} {NARANJA}FOLLOWERS{RESET}      "
                f"{MORADO}►{RESET} Sin cambios ({event.total} total)"
            )
            return

        CONSOLE.print(
            f"{timestamp} {NARANJA}FOLLOWERS{RESET}      "
            f"{MORADO}►{RESET} Sincronización finalizada ({event.total} total):"
        )

        if event.new_count:
            CONSOLE.print(f"  [green][+] Nuevos seguidores ({event.new_count}):[/]")
            for label in event.new_labels:
                CONSOLE.print(f"    [green]●[/] {label}")

        if event.lost_count:
            CONSOLE.print(f"  [red][-] Dejaron de seguir ({event.lost_count}):[/]")
            for label in event.lost_labels:
                CONSOLE.print(f"    [red]●[/] {label}")

    async def _on_follower_progress(self, event: FollowerProgressEvent) -> None:
        # Evitar inundar la terminal y problemas de \r con patch_stdout en Windows
        interval = 100
        if event.total > 5000:
            interval = 1000
        elif event.total > 1000:
            interval = 500

        if (
            event.count == 1
            or event.count % interval == 0
            or event.count == event.total
        ):
            timestamp = format_timestamp()
            CONSOLE.print(
                f"{timestamp} {NARANJA}FOLLOWERS{RESET}      "
                f"{MORADO}►{RESET} Sincronizando seguidores... "
                f"{event.count}/{event.total}"
            )

    async def _on_clip_created(self, event: ClipCreatedEvent) -> None:
        timestamp = format_timestamp()
        url_link = f"[link={event.url}]{event.url}[/link]"
        CONSOLE.print(
            f"{timestamp} {VERDE}{BOLD}[CLIP CREADO]{RESET} "
            f"{MORADO}►{RESET} ¡Nuevo clip generado! URL: {url_link}"
        )

    # ── Twitch EventSub Alerts ────────────────────────────────────────────────
    async def _on_twitch_follow(self, event: TwitchFollowEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold green][FOLLOW][/] "
            f"[bold]{event.display_name}[/] comenzó a seguir el canal!"
        )

    async def _on_twitch_raid(self, event: TwitchRaidEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold magenta][RAID][/] "
            f"[bold]{event.from_display_name}[/] nos hizo raid con "
            f"[bold cyan]{event.viewer_count}[/] espectadores!"
        )

    async def _on_twitch_subscribe(self, event: TwitchSubscribeEvent) -> None:
        timestamp = format_timestamp()
        regalo = " (Regalo)" if event.is_gift else ""
        CONSOLE.print(
            f"{timestamp} [bold green][SUB][/] "
            f"[bold]{event.display_name}[/] se suscribió en Tier "
            f"[bold cyan]{event.tier}[/]{regalo}!"
        )

    async def _on_twitch_sub_gift(self, event: TwitchSubscriptionGiftEvent) -> None:
        timestamp = format_timestamp()
        acumulado = (
            f" (Acumulado: {event.cumulative_total})" if event.cumulative_total else ""
        )
        donante = "Anónimo" if event.is_anonymous else event.display_name
        CONSOLE.print(
            f"{timestamp} [bold green][SUB GIFT][/] "
            f"[bold]{donante}[/] regaló [bold cyan]{event.total}[/] "
            f"suscripciones de Tier [bold cyan]{event.tier}[/]{acumulado}!"
        )

    async def _on_twitch_sub_message(
        self, event: TwitchSubscriptionMessageEvent
    ) -> None:
        timestamp = format_timestamp()
        racha = f" (Racha: {event.streak_months} meses)" if event.streak_months else ""
        msg_str = f' - Mensaje: "{event.message}"' if event.message else ""
        CONSOLE.print(
            f"{timestamp} [bold green][SUB RESUB][/] "
            f"[bold]{event.display_name}[/] se resuscribió por "
            f"[bold cyan]{event.cumulative_months}[/] meses{racha}!{msg_str}"
        )

    async def _on_twitch_cheer(self, event: TwitchCheerEvent) -> None:
        timestamp = format_timestamp()
        donante = "Anónimo" if event.is_anonymous else event.display_name
        msg_str = f' - Mensaje: "{event.message}"' if event.message else ""
        CONSOLE.print(
            f"{timestamp} [bold yellow][CHEER][/] "
            f"[bold]{donante}[/] envió [bold cyan]{event.bits}[/] bits!{msg_str}"
        )

    async def _on_twitch_points_redeem(
        self, event: TwitchChannelPointsRedeemEvent
    ) -> None:
        timestamp = format_timestamp()
        input_str = f' - Entrada: "{event.user_input}"' if event.user_input else ""
        CONSOLE.print(
            f"{timestamp} [bold cyan][PUNTOS][/] "
            f"[bold]{event.display_name}[/] canjeó [bold]{event.reward_title}[/] "
            f"por [bold cyan]{event.reward_cost}[/] puntos!{input_str}"
        )

    async def _on_prediction_begin(self, event: TwitchPredictionBeginEvent) -> None:
        timestamp = format_timestamp()
        opciones = ", ".join(event.outcomes)
        CONSOLE.print(
            f"{timestamp} [bold blue][PREDICCION INICIO][/] "
            f'Predicción "[bold]{event.title}[/]" iniciada! '
            f"Opciones: [cyan]{opciones}[/]"
        )

    async def _on_prediction_progress(
        self, event: TwitchPredictionProgressEvent
    ) -> None:
        timestamp = format_timestamp()
        partes = []
        for opt, pts, users in event.outcomes_votes:
            partes.append(f"{opt}: {pts} pts ({users} users)")
        progreso = " | ".join(partes)
        CONSOLE.print(
            f"{timestamp} [bold blue][PREDICCION PROGRESO][/] "
            f'"[bold]{event.title}[/]": {progreso}'
        )

    async def _on_prediction_lock(self, event: TwitchPredictionLockEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold blue][PREDICCION CERRADA][/] "
            f'Apuestas para "[bold]{event.title}[/]" cerradas!'
        )

    async def _on_prediction_end(self, event: TwitchPredictionEndEvent) -> None:
        timestamp = format_timestamp()
        resultado = (
            f"Ganador: [bold green]{event.winning_outcome_title}[/]"
            if event.winning_outcome_title
            else f"Estado: {event.status}"
        )
        CONSOLE.print(
            f"{timestamp} [bold blue][PREDICCION FIN][/] "
            f'Predicción "[bold]{event.title}[/]" terminada! {resultado}'
        )

    async def _on_twitch_ban(self, event: TwitchBanEvent) -> None:
        timestamp = format_timestamp()
        tipo = (
            "permanente" if event.permanent else f"timeout de {event.duration_seconds}s"
        )
        razon = f' - Razón: "{event.reason}"' if event.reason else ""
        CONSOLE.print(
            f"{timestamp} [bold red][BAN][/] "
            f"Usuario [bold]{event.display_name}[/] fue sancionado ({tipo}) "
            f"por el moderador [bold]{event.moderator_name}[/].{razon}"
        )

    async def _on_twitch_unban(self, event: TwitchUnbanEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold red][UNBAN][/] "
            f"Usuario [bold]{event.display_name}[/] fue desbaneado "
            f"por el moderador [bold]{event.moderator_name}[/]!"
        )

    async def _on_twitch_chat_clear(self, event: TwitchChatClearEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold red][CHAT CLEAR][/] "
            "El chat fue limpiado por un moderador."
        )

    async def _on_twitch_chat_clear_user(self, event: TwitchChatClearUserEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold red][PURGA][/] "
            f"Los mensajes del usuario [bold]{event.display_name}[/] "
            "fueron eliminados por un moderador."
        )

    async def _on_twitch_message_delete(self, event: TwitchMessageDeleteEvent) -> None:
        timestamp = format_timestamp()
        CONSOLE.print(
            f"{timestamp} [bold red][MENSAJE BORRADO][/] "
            f"Se borró un mensaje del usuario [bold]{event.display_name}[/] "
            f"({event.message_text})."
        )
