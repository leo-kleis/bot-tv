from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot_tv.agent.models import AVAILABLE_MODELS

if TYPE_CHECKING:
    from bot_tv.agent.models import ModelConfig


@dataclass
class RateLimitStatus:
    model: str
    display_name: str
    rpm_used: int
    rpm_limit: int
    rpm_remaining: int
    rpd_used: int
    rpd_limit: int
    rpd_remaining: int
    next_slot_in: float | None
    is_blocked: bool
    blocked_reason: str | None


class ModelTracker:
    """Tracker de solicitudes por modelo usando ventana deslizante y hora real."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._minute_window: deque[float] = deque()
        self._day_window: deque[float] = deque()
        self._blocked_until: float = 0.0
        self._block_reason: str | None = None

    def _purge(self) -> None:
        now = time.time()
        while self._minute_window and (now - self._minute_window[0]) > 60:
            self._minute_window.popleft()
        while self._day_window and (now - self._day_window[0]) > 86400:
            self._day_window.popleft()

    def can_request(self) -> bool:
        if (
            not self.config.enabled
            or self.config.rpm_limit <= 0
            or self.config.rpd_limit <= 0
        ):
            return False
        self._purge()
        now = time.time()
        if now < self._blocked_until:
            return False
        return (
            len(self._minute_window) < self.config.rpm_limit
            and len(self._day_window) < self.config.rpd_limit
        )

    def record_request(self) -> None:
        self._purge()
        now = time.time()
        self._minute_window.append(now)
        self._day_window.append(now)

    def record_rate_limit_hit(self, retry_after: float | None = None) -> None:
        now = time.time()
        wait_time = retry_after if retry_after is not None else 60.0
        self._blocked_until = now + wait_time
        self._block_reason = "HTTP 429 Quota Exceeded"

    def get_status(self) -> RateLimitStatus:
        self._purge()
        now = time.time()

        next_slot_in: float | None = None
        is_blocked = False
        reason = None

        if (
            not self.config.enabled
            or self.config.rpm_limit <= 0
            or self.config.rpd_limit <= 0
        ):
            is_blocked = True
            reason = "Deshabilitado"
        elif now < self._blocked_until:
            is_blocked = True
            next_slot_in = self._blocked_until - now
            reason = self._block_reason or "Bloqueado por rate limit"
        elif len(self._minute_window) >= self.config.rpm_limit:
            is_blocked = True
            next_slot_in = 60.0 - (now - self._minute_window[0])
            reason = "Límite RPM alcanzado"
        elif len(self._day_window) >= self.config.rpd_limit:
            is_blocked = True
            next_slot_in = 86400.0 - (now - self._day_window[0])
            reason = "Límite RPD alcanzado"

        if next_slot_in is not None and next_slot_in < 0:
            next_slot_in = 0.0

        rpm_used = len(self._minute_window)
        rpd_used = len(self._day_window)

        return RateLimitStatus(
            model=self.config.name,
            display_name=self.config.display_name,
            rpm_used=rpm_used,
            rpm_limit=self.config.rpm_limit,
            rpm_remaining=max(0, self.config.rpm_limit - rpm_used),
            rpd_used=rpd_used,
            rpd_limit=self.config.rpd_limit,
            rpd_remaining=max(0, self.config.rpd_limit - rpd_used),
            next_slot_in=next_slot_in,
            is_blocked=is_blocked,
            blocked_reason=reason,
        )


class RateLimiter:
    """Gestor global de rate limiting para todos los modelos con persistencia."""

    def __init__(self) -> None:
        self._trackers: dict[str, ModelTracker] = {
            name: ModelTracker(cfg) for name, cfg in AVAILABLE_MODELS.items()
        }

    def can_request(self, model: str) -> bool:
        tracker = self._trackers.get(model)
        if not tracker:
            return False
        return tracker.can_request()

    def record_request(self, model: str) -> None:
        tracker = self._trackers.get(model)
        if tracker:
            tracker.record_request()

    def record_rate_limit_hit(
        self, model: str, retry_after: float | None = None
    ) -> None:
        tracker = self._trackers.get(model)
        if tracker:
            tracker.record_rate_limit_hit(retry_after)

    def get_status(self, model: str) -> RateLimitStatus:
        tracker = self._trackers.get(model)
        if not tracker:
            raise ValueError(f"Modelo desconocido: {model}")
        return tracker.get_status()

    def get_all_status(self) -> list[RateLimitStatus]:
        return [tracker.get_status() for tracker in self._trackers.values()]

    def find_best_fallback(self, exclude_model: str) -> str | None:
        """Encuentra el modelo habilitado con más RPM restante."""
        best_model: str | None = None
        max_remaining = -1

        for name, tracker in self._trackers.items():
            if name == exclude_model:
                continue
            if not tracker.can_request():
                continue

            status = tracker.get_status()
            if status.rpm_remaining > max_remaining:
                max_remaining = status.rpm_remaining
                best_model = name

        return best_model

    def load_history(self, history: list[tuple[str, float, str]]) -> None:
        """Carga el historial de consumos y bloqueos de la base de datos."""
        now = time.time()
        for model, timestamp, type_str in history:
            tracker = self._trackers.get(model)
            if not tracker:
                continue

            if type_str == "request":
                # Reconstruir deques solo si están dentro de la ventana deslizante
                if (now - timestamp) <= 60:
                    tracker._minute_window.append(timestamp)
                if (now - timestamp) <= 86400:
                    tracker._day_window.append(timestamp)
            elif type_str.startswith("hit:"):
                try:
                    retry_after = float(type_str.split(":")[1])
                except ValueError, IndexError:
                    retry_after = 60.0
                blocked_until = timestamp + retry_after
                if blocked_until > now:
                    tracker._blocked_until = blocked_until
                    tracker._block_reason = "Bloqueado (Cargado de DB)"
