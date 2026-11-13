from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from bot_tv.agent.models import AVAILABLE_MODELS

if TYPE_CHECKING:
    from bot_tv.agent.models import ModelConfig

LOGGER = logging.getLogger(__name__)

SECONDS_PER_MINUTE: Final[float] = 60.0
SECONDS_PER_DAY: Final[float] = 86400.0
DEFAULT_RETRY_AFTER_SECONDS: Final[float] = 60.0
MAX_FUTURE_SKEW_SECONDS: Final[float] = 5.0


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
        minute_cap = max(1, config.rpm_limit)
        day_cap = max(1, config.rpd_limit)
        self._minute_window: deque[float] = deque(maxlen=minute_cap)
        self._day_window: deque[float] = deque(maxlen=day_cap)
        self._blocked_until: float = 0.0
        self._block_reason: str | None = None

    def reset(self) -> None:
        """Limpia por completo las ventanas y el estado de bloqueo."""
        self._minute_window.clear()
        self._day_window.clear()
        self._blocked_until = 0.0
        self._block_reason = None

    def _is_enabled_with_quotas(self) -> bool:
        return (
            self.config.enabled
            and self.config.rpm_limit > 0
            and self.config.rpd_limit > 0
        )

    def _purge(self, now: float | None = None) -> int:
        current = time.time() if now is None else now
        pruned = 0

        while (
            self._minute_window
            and (current - self._minute_window[0]) > SECONDS_PER_MINUTE
        ):
            self._minute_window.popleft()
            pruned += 1

        while self._day_window and (current - self._day_window[0]) > SECONDS_PER_DAY:
            self._day_window.popleft()
            pruned += 1

        if self._blocked_until > 0.0 and current >= self._blocked_until:
            self._blocked_until = 0.0
            self._block_reason = None
            pruned += 1

        return pruned

    def prune_stale(self, now: float | None = None) -> int:
        """Elimina entradas expiradas de las ventanas y reinicia bloqueos vencidos."""
        return self._purge(now)

    def can_request(self) -> bool:
        if not self._is_enabled_with_quotas():
            return False
        now = time.time()
        self._purge(now)
        if now < self._blocked_until:
            return False
        return (
            len(self._minute_window) < self.config.rpm_limit
            and len(self._day_window) < self.config.rpd_limit
        )

    def record_request(self) -> None:
        now = time.time()
        self._purge(now)
        self._minute_window.append(now)
        self._day_window.append(now)

    def record_rate_limit_hit(self, retry_after: float | None = None) -> None:
        now = time.time()
        wait_time = (
            retry_after
            if retry_after is not None and retry_after > 0.0
            else DEFAULT_RETRY_AFTER_SECONDS
        )
        self._blocked_until = max(self._blocked_until, now + wait_time)
        self._block_reason = "HTTP 429 Quota Exceeded"

    def get_status(self) -> RateLimitStatus:
        now = time.time()
        self._purge(now)

        next_slot_in: float | None = None
        is_blocked = False
        reason: str | None = None

        if not self._is_enabled_with_quotas():
            is_blocked = True
            reason = "Deshabilitado"
        elif now < self._blocked_until:
            is_blocked = True
            next_slot_in = self._blocked_until - now
            reason = self._block_reason or "Bloqueado por rate limit"
        elif len(self._minute_window) >= self.config.rpm_limit:
            is_blocked = True
            next_slot_in = SECONDS_PER_MINUTE - (now - self._minute_window[0])
            reason = "Límite RPM alcanzado"
        elif len(self._day_window) >= self.config.rpd_limit:
            is_blocked = True
            next_slot_in = SECONDS_PER_DAY - (now - self._day_window[0])
            reason = "Límite RPD alcanzado"

        if next_slot_in is not None and next_slot_in < 0.0:
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

    def prune_stale(self, now: float | None = None) -> int:
        """Purga entradas vencidas y descarta buckets obsoletos en los trackers."""
        current = time.time() if now is None else now
        pruned = 0

        stale_models = [name for name in self._trackers if name not in AVAILABLE_MODELS]
        for name in stale_models:
            del self._trackers[name]
            pruned += 1

        for tracker in self._trackers.values():
            pruned += tracker.prune_stale(current)
        return pruned

    def can_request(self, model: str) -> bool:
        tracker = self._trackers.get(model)
        if not tracker:
            return False
        return tracker.can_request()

    def record_request(self, model: str) -> None:
        now = time.time()
        self.prune_stale(now)
        tracker = self._trackers.get(model)
        if tracker:
            tracker.record_request()

    def record_rate_limit_hit(
        self, model: str, retry_after: float | None = None
    ) -> None:
        now = time.time()
        self.prune_stale(now)
        tracker = self._trackers.get(model)
        if tracker:
            tracker.record_rate_limit_hit(retry_after)

    def get_status(self, model: str) -> RateLimitStatus:
        tracker = self._trackers.get(model)
        if not tracker:
            raise ValueError(f"Modelo desconocido: {model}")
        return tracker.get_status()

    def get_all_status(self) -> list[RateLimitStatus]:
        self.prune_stale()
        return [tracker.get_status() for tracker in self._trackers.values()]

    def find_best_fallback(self, exclude_model: str) -> str | None:
        """Encuentra el modelo habilitado con más RPM restante."""
        self.prune_stale()
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
        for tracker in self._trackers.values():
            tracker.reset()

        # Agrupar y ordenar por timestamp para mantener el invariante monótono de deque.
        day_entries: dict[str, list[float]] = defaultdict(list)

        for model, timestamp, type_str in history:
            tracker = self._trackers.get(model)
            if not tracker:
                continue
            if timestamp > now + MAX_FUTURE_SKEW_SECONDS:
                continue

            if type_str == "request":
                if (now - timestamp) <= SECONDS_PER_DAY:
                    day_entries[model].append(timestamp)
            elif type_str.startswith("hit:"):
                try:
                    retry_after = float(type_str.split(":", 1)[1])
                except ValueError, IndexError:
                    LOGGER.debug(
                        "Valor retry_after inválido en historial (%s): %r",
                        model,
                        type_str,
                    )
                    retry_after = DEFAULT_RETRY_AFTER_SECONDS
                blocked_until = timestamp + max(0.0, retry_after)
                if blocked_until > now:
                    tracker._blocked_until = max(tracker._blocked_until, blocked_until)
                    tracker._block_reason = "Bloqueado (Cargado de DB)"

        for model, timestamps in day_entries.items():
            tracker = self._trackers[model]
            timestamps.sort()
            for ts in timestamps:
                tracker._day_window.append(ts)
                if (now - ts) <= SECONDS_PER_MINUTE:
                    tracker._minute_window.append(ts)
