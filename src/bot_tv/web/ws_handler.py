"""WebSocket handler: consume el EventBus y transmite eventos a clientes web."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from bot_tv.events import (
    AgentResponseEvent,
    BotLogEvent,
    ChatMessageEvent,
    ClipCreatedEvent,
    FollowerProgressEvent,
    FollowerSyncEvent,
    StreamOfflineEvent,
    StreamOnlineEvent,
    StreamUpdateEvent,
    TwitchBanEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchCheerEvent,
    TwitchFollowEvent,
    TwitchIRCStatusEvent,
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
    UserNicknameUpdatedEvent,
    UserPartEvent,
    UserRoleUpdatedEvent,
    ViewerUpdateEvent,
)
from bot_tv.utils.env import CORS_ORIGINS, IDLE_SHUTDOWN_SECONDS, MAX_WS_CLIENTS

if TYPE_CHECKING:
    from collections.abc import Callable

    from bot_tv.bot import Bot
    from bot_tv.event_bus import EventBus

LOGGER = logging.getLogger(__name__)

WS_SEND_TIMEOUT_SECONDS = 2.0
WS_POLICY_VIOLATION_CODE = 1008
MAX_SERIALIZED_CACHE_SIZE = 4096
_DEFAULT_CORS_ORIGINS = CORS_ORIGINS

# Mapeo tipo de evento Python → tipo de mensaje JSON
EVENT_TYPE_MAP: dict[type, str] = {
    ChatMessageEvent: "chat_message",
    UserJoinEvent: "user_join",
    UserPartEvent: "user_part",
    UserRoleUpdatedEvent: "user_role_updated",
    UserNicknameUpdatedEvent: "user_nickname_updated",
    StreamOnlineEvent: "stream_online",
    StreamOfflineEvent: "stream_offline",
    StreamUpdateEvent: "stream_update",
    ViewerUpdateEvent: "viewer_update",
    FollowerSyncEvent: "follower_sync",
    FollowerProgressEvent: "follower_progress",
    AgentResponseEvent: "agent_response",
    ClipCreatedEvent: "clip_created",
    BotLogEvent: "bot_log",
    TwitchFollowEvent: "twitch_follow",
    TwitchRaidEvent: "twitch_raid",
    TwitchSubscribeEvent: "twitch_subscribe",
    TwitchSubscriptionGiftEvent: "twitch_sub_gift",
    TwitchSubscriptionMessageEvent: "twitch_sub_message",
    TwitchCheerEvent: "twitch_cheer",
    TwitchChannelPointsRedeemEvent: "twitch_points_redeem",
    TwitchPredictionBeginEvent: "prediction_begin",
    TwitchPredictionProgressEvent: "prediction_progress",
    TwitchPredictionLockEvent: "prediction_lock",
    TwitchPredictionEndEvent: "prediction_end",
    TwitchBanEvent: "twitch_ban",
    TwitchUnbanEvent: "twitch_unban",
    TwitchChatClearEvent: "twitch_chat_clear",
    TwitchChatClearUserEvent: "twitch_chat_clear_user",
    TwitchMessageDeleteEvent: "twitch_message_delete",
    TwitchIRCStatusEvent: "irc_status",
}

# Tipos de eventos que se incluyen en el historial inicial al conectar
HISTORY_EVENT_TYPES: list[type] = [
    ChatMessageEvent,
    UserRoleUpdatedEvent,
    UserNicknameUpdatedEvent,
    StreamOnlineEvent,
    StreamOfflineEvent,
    ViewerUpdateEvent,
    FollowerSyncEvent,
    AgentResponseEvent,
    ClipCreatedEvent,
    TwitchFollowEvent,
    TwitchRaidEvent,
    TwitchSubscribeEvent,
    TwitchSubscriptionGiftEvent,
    TwitchSubscriptionMessageEvent,
    TwitchCheerEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchPredictionBeginEvent,
    TwitchPredictionEndEvent,
    TwitchBanEvent,
    TwitchUnbanEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchMessageDeleteEvent,
    TwitchIRCStatusEvent,
]


def _serialize_dict(event: object) -> dict[str, Any] | None:
    """Convierte un evento en diccionario {"type": ..., "data": ...}."""
    event_type = type(event)
    type_name = EVENT_TYPE_MAP.get(event_type)
    if type_name is None:
        return None

    try:
        data = asdict(event)  # type: ignore[call-overload]
        return {"type": type_name, "data": data}
    except Exception:
        LOGGER.exception("Error al serializar evento %s", event_type.__name__)
        return None


def _serialize(event: object) -> str | None:
    """Serializa un evento a JSON. Retorna None si el tipo no está mapeado."""
    payload = _serialize_dict(event)
    if payload is None:
        return None

    try:
        return json.dumps(payload)
    except Exception:
        LOGGER.exception("Error al codificar JSON del evento %s", type(event).__name__)
        return None


class WebSocketManager:
    """Gestiona las conexiones WebSocket activas y el broadcast de eventos."""

    def __init__(self, event_bus: EventBus, bot: Bot | None = None) -> None:
        self._event_bus = event_bus
        self._bot = bot
        self._connections: set[WebSocket] = set()
        self._registered = False
        self._shutdown_callback: Callable[[], None] | None = None
        self._idle_task: asyncio.Task[None] | None = None
        # Caché acotada por id(evento) con ref fuerte para reutilizar en reconexiones
        self._serialized_cache: OrderedDict[int, tuple[object, str]] = OrderedDict()

    def set_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """Registra el callback para apagar el servidor cuando expira el idle timer."""
        self._shutdown_callback = callback
        if IDLE_SHUTDOWN_SECONDS > 0 and not self._connections:
            self._schedule_idle_shutdown()

    def _cancel_idle_shutdown(self) -> None:
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    def _schedule_idle_shutdown(self) -> None:
        if IDLE_SHUTDOWN_SECONDS <= 0 or self._shutdown_callback is None:
            return
        self._cancel_idle_shutdown()

        async def _wait_and_shutdown() -> None:
            await asyncio.sleep(IDLE_SHUTDOWN_SECONDS)
            if not self._connections and self._shutdown_callback is not None:
                LOGGER.warning(
                    "Sin usuarios conectados durante %ds (IDLE_SHUTDOWN_SECONDS). "
                    "Apagando servidor automáticamente (modo bajo demanda)...",
                    IDLE_SHUTDOWN_SECONDS,
                )
                self._shutdown_callback()

        self._idle_task = asyncio.create_task(_wait_and_shutdown())

    def register(self) -> None:
        """Suscribe al EventBus para todos los tipos de evento. Llámalo una vez."""
        if self._registered:
            return
        self._registered = True
        for event_type in EVENT_TYPE_MAP:
            self._event_bus.subscribe(event_type, self._broadcast)

    def _serialize_cached(self, event: object) -> str | None:
        """Serializa un evento reutilizando JSON cacheado mientras siga en memoria."""
        event_id = id(event)
        cached = self._serialized_cache.get(event_id)
        if cached is not None and cached[0] is event:
            self._serialized_cache.move_to_end(event_id)
            return cached[1]

        serialized = _serialize(event)
        if serialized is None:
            return None

        self._serialized_cache[event_id] = (event, serialized)
        if len(self._serialized_cache) > MAX_SERIALIZED_CACHE_SIZE:
            self._serialized_cache.popitem(last=False)
        return serialized

    async def _send_with_timeout(self, ws: WebSocket, message: str) -> WebSocket | None:
        """Envía mensaje a un cliente con timeout; retorna el cliente si falló."""
        if ws.client_state != WebSocketState.CONNECTED:
            return ws
        try:
            await asyncio.wait_for(
                ws.send_text(message), timeout=WS_SEND_TIMEOUT_SECONDS
            )
            return None
        except TimeoutError, WebSocketDisconnect, RuntimeError, OSError:
            LOGGER.debug("Fallo al enviar mensaje WebSocket; descartando cliente")
            return ws

    async def _send_to_all(self, message: str) -> None:
        """Envía un mensaje en paralelo a un snapshot de las conexiones activas."""
        clients = tuple(self._connections)
        if not clients:
            return

        results = await asyncio.gather(
            *(self._send_with_timeout(ws, message) for ws in clients)
        )
        dead = {ws for ws in results if ws is not None}
        if dead:
            self._connections -= dead
            if not self._connections:
                self._schedule_idle_shutdown()

    async def _broadcast(self, event: object) -> None:
        """Envía el evento serializado a todas las conexiones activas."""
        if not self._connections:
            return

        message = self._serialize_cached(event)
        if message is None:
            return

        await self._send_to_all(message)

    async def broadcast_dev_reload(self) -> None:
        """Envía una señal dev_reload a todas las conexiones activas."""
        if not self._connections:
            return

        message = json.dumps({"type": "dev_reload"})
        await self._send_to_all(message)

    async def close_all(self) -> None:
        """Cierra activamente todas las conexiones WebSocket al apagar el servidor."""
        self._cancel_idle_shutdown()
        clients = tuple(self._connections)
        self._connections.clear()
        for ws in clients:
            if ws.client_state != WebSocketState.CONNECTED:
                continue
            try:
                await ws.close(code=1001)
            except WebSocketDisconnect, RuntimeError, OSError:
                LOGGER.debug("Cliente WebSocket ya cerrado al apagar servidor")

    async def handle(self, ws: WebSocket) -> None:
        """Maneja el ciclo de vida de una conexión WebSocket entrante."""
        from bot_tv.web.server import (
            is_allowed_request_origin,
            is_authorized_request,
            is_valid_host_header,
        )

        query_token = ws.query_params.get("token", "").strip()
        if not is_authorized_request(ws.headers, ws.cookies, query_token=query_token):
            LOGGER.warning("Conexión WebSocket rechazada: WEB_ACCESS_TOKEN inválido.")
            await ws.close(code=WS_POLICY_VIOLATION_CODE)
            return

        override_cors = (
            CORS_ORIGINS if CORS_ORIGINS is not _DEFAULT_CORS_ORIGINS else None
        )
        host_values = ws.headers.getlist("host")
        if len(host_values) != 1 or not is_valid_host_header(
            host_values[0], ws.scope, cors_origins=override_cors
        ):
            LOGGER.warning(
                "Conexión WebSocket rechazada por cabecera Host inválida: %s",
                host_values[0] if host_values else "<ausente>",
            )
            await ws.close(code=WS_POLICY_VIOLATION_CODE)
            return

        if not is_allowed_request_origin(
            ws.headers, ws.scope, cors_origins=override_cors
        ):
            LOGGER.warning(
                "Conexión WS rechazada por Origin inválido: %s (Host: %s)",
                ws.headers.get("origin", "<ausente>"),
                host_values[0],
            )
            await ws.close(code=WS_POLICY_VIOLATION_CODE)
            return

        if len(self._connections) >= MAX_WS_CLIENTS:
            LOGGER.warning(
                "Conexión WebSocket rechazada: límite de clientes alcanzado (%d)",
                MAX_WS_CLIENTS,
            )
            await ws.close(code=WS_POLICY_VIOLATION_CODE)
            return

        await ws.accept()
        self._connections.add(ws)
        self._cancel_idle_shutdown()
        LOGGER.info(
            "WebSocket conectado (%d/%d clientes activos)",
            len(self._connections),
            MAX_WS_CLIENTS,
        )

        try:
            # Enviar historial acumulado de la sesión actual en lote
            if not await self._send_history(ws):
                return

            # Señal de fin de historial
            try:
                await ws.send_text('{"type":"history_end"}')
            except WebSocketDisconnect, RuntimeError, OSError:
                LOGGER.debug("Cliente desconectado al enviar history_end")
                return

            # Mantener la conexión abierta hasta que el cliente desconecte
            while True:
                data = await ws.receive_text()
                LOGGER.debug("Mensaje WS recibido (ignorado): %s", data[:100])

        except WebSocketDisconnect, asyncio.CancelledError, OSError:
            pass
        except Exception:
            LOGGER.exception("Error en WebSocket handler")
        finally:
            self._connections.discard(ws)
            LOGGER.info(
                "WebSocket desconectado (%d/%d clientes activos)",
                len(self._connections),
                MAX_WS_CLIENTS,
            )
            if not self._connections:
                self._schedule_idle_shutdown()

    async def _send_history(self, ws: WebSocket) -> bool:
        """Envía el historial acumulado del EventBus en un único lote al cliente."""
        all_events: list[object] = []
        for event_type in HISTORY_EVENT_TYPES:
            all_events.extend(self._event_bus.get_history(event_type))

        try:
            all_events.sort(key=lambda e: str(getattr(e, "timestamp", "")))
        except TypeError:
            LOGGER.exception("Error ordenando historial de eventos por timestamp")

        if self._bot and self._bot.irc is not None:
            all_events.extend(list(self._bot.irc.connected_users.values()))
            all_events.extend(list(self._bot.irc.parted_users.values()))

        batch_items: list[str] = []
        for event in all_events:
            serialized = self._serialize_cached(event)
            if serialized is not None:
                batch_items.append(serialized)

        if batch_items:
            payload = f'{{"type":"history_batch","data":[{",".join(batch_items)}]}}'
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect, RuntimeError, OSError:
                LOGGER.debug("Cliente desconectado al enviar lote de historial")
                return False
        return True
