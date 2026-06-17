"""EventBus: pub/sub asíncrono con buffer circular para reconexión."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TypeVar

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

# Tamaño máximo del buffer por tipo de evento
DEFAULT_BUFFER_SIZE = 500

# Tipo de callback suscriptor
Subscriber = Callable[[object], Awaitable[None]]


class EventBus:
    """Pub/sub asíncrono con buffer circular.

    Permite que múltiples consumers se suscriban a tipos de eventos.
    Mantiene un historial en memoria por tipo para que clientes que
    reconectan puedan recibir eventos pasados de la sesión actual.
    """

    def __init__(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        self._buffer_size = buffer_size
        self._subscribers: dict[type, list[Subscriber]] = {}
        self._history: dict[type, deque[object]] = {}

    def subscribe(
        self,
        event_type: type[T],
        callback: Callable[[T], Awaitable[None]],
    ) -> None:
        """Registra un callback para un tipo de evento.

        Se puede llamar múltiples veces con distintos callbacks
        para el mismo tipo — todos serán notificados.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        # TypeVar no es perfectamente covariante aquí, el cast es seguro
        self._subscribers[event_type].append(callback)  # type: ignore[arg-type]

    async def emit(self, event: object) -> None:
        """Despacha un evento a todos los suscriptores registrados para su tipo.

        Guarda el evento en el buffer histórico antes de despachar.
        Los errores en suscriptores individuales se loguean pero no
        interrumpen el despacho al resto.
        """
        event_type = type(event)

        # Guardar en historial
        if event_type not in self._history:
            self._history[event_type] = deque(maxlen=self._buffer_size)
        self._history[event_type].append(event)

        # Despachar a suscriptores
        subscribers = self._subscribers.get(event_type, [])
        for callback in subscribers:
            try:
                await callback(event)
            except Exception:
                LOGGER.exception(
                    "Error en suscriptor '%s' para evento '%s'",
                    callback.__qualname__,
                    event_type.__name__,
                )

    def get_history(
        self,
        event_type: type | None = None,
        limit: int = 100,
    ) -> list[object]:
        """Retorna eventos almacenados en el buffer.

        Si se especifica `event_type`, retorna solo eventos de ese tipo.
        Si no, retorna todos los tipos ordenados por timestamp (best-effort).
        El `limit` aplica por tipo si se filtra, o al total si no.
        """
        if event_type is not None:
            history = self._history.get(event_type, deque())
            events = list(history)
            return events[-limit:] if len(events) > limit else events

        # Todos los tipos: aplanar y ordenar por timestamp si tienen el campo
        all_events: list[object] = []
        for events_deque in self._history.values():
            all_events.extend(events_deque)

        # Ordenar por timestamp si los eventos tienen ese atributo
        with contextlib.suppress(Exception):
            all_events.sort(key=lambda e: getattr(e, "timestamp", ""))

        return all_events[-limit:] if len(all_events) > limit else all_events

    def clear_history(self) -> None:
        """Limpia todo el historial (útil para tests o reinicio de sesión)."""
        self._history.clear()

    @property
    def subscriber_count(self) -> int:
        """Cantidad total de suscriptores registrados."""
        return sum(len(subs) for subs in self._subscribers.values())

    def get_tasks(self) -> list[asyncio.Task[None]]:
        """Retorna lista vacía — compatibilidad futura para cleanup."""
        return []
