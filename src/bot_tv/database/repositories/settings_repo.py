from __future__ import annotations

import time
from typing import TYPE_CHECKING

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    import asyncpg

_API_LOG_RETENTION_SECONDS = 86_400.0
_API_LOG_PURGE_INTERVAL_SECONDS = 3_600.0


class SettingsRepository(BaseRepository):
    """Repositorio para gestionar las tablas app_settings y api_consumption_log."""

    def __init__(self, db: asyncpg.Pool) -> None:
        super().__init__(db)
        self._last_log_purge_monotonic: float | None = None

    async def get_setting(self, key: str, default: str) -> str:
        """Obtiene un valor de configuración de la base de datos."""
        row = await self._fetchrow(
            "SELECT value FROM app_settings WHERE key = $1",
            key,
            context_label="get_setting",
        )
        return str(row["value"]) if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """Guarda o actualiza un valor de configuración."""
        await self._execute(
            "INSERT INTO app_settings (key, value) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            key,
            value,
            context_label="set_setting",
        )

    async def log_api_consumption(
        self, model: str, timestamp: float, type_str: str
    ) -> None:
        """Registra consumo de API amortizando la purga de registros expirados."""
        now_monotonic = time.monotonic()
        should_purge = (
            self._last_log_purge_monotonic is None
            or (now_monotonic - self._last_log_purge_monotonic)
            >= _API_LOG_PURGE_INTERVAL_SECONDS
        )
        if should_purge:
            cutoff = time.time() - _API_LOG_RETENTION_SECONDS
            query = """
                WITH purged AS (
                    DELETE FROM api_consumption_log WHERE timestamp <= $4
                )
                INSERT INTO api_consumption_log (model, timestamp, type)
                VALUES ($1, $2, $3)
            """
            await self._execute(
                query,
                model,
                timestamp,
                type_str,
                cutoff,
                context_label="log_api_consumption_purge",
            )
            self._last_log_purge_monotonic = now_monotonic
            return

        await self._execute(
            "INSERT INTO api_consumption_log (model, timestamp, type) "
            "VALUES ($1, $2, $3)",
            model,
            timestamp,
            type_str,
            context_label="log_api_consumption",
        )

    async def get_api_consumption_history(self) -> list[tuple[str, float, str]]:
        """Obtiene el historial de consumo de API de las últimas 24 horas."""
        cutoff = time.time() - _API_LOG_RETENTION_SECONDS
        query = """
            WITH purged AS (
                DELETE FROM api_consumption_log WHERE timestamp <= $1
            )
            SELECT model, timestamp, type
            FROM api_consumption_log
            WHERE timestamp > $1
            ORDER BY timestamp ASC
        """
        rows = await self._fetch(
            query,
            cutoff,
            context_label="get_api_consumption_history",
        )
        self._last_log_purge_monotonic = time.monotonic()
        return [(row["model"], row["timestamp"], row["type"]) for row in rows]
