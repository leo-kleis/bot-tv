from __future__ import annotations

import time

import asyncpg

from bot_tv.database.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    """Repositorio para gestionar las tablas app_settings y api_consumption_log."""

    async def get_setting(self, key: str, default: str) -> str:
        """Obtiene un valor de configuración de la base de datos."""
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT value FROM app_settings WHERE key = $1", key
            )
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """Guarda o actualiza un valor de configuración."""
        async with self._db.acquire() as conn:
            await conn.execute(
                "INSERT INTO app_settings (key, value) VALUES ($1, $2) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                key,
                value,
            )

    async def log_api_consumption(
        self, model: str, timestamp: float, type_str: str
    ) -> None:
        """Registra un consumo de API o un bloqueo por rate limit."""
        async with self._db.acquire() as conn:
            await conn.execute(
                "INSERT INTO api_consumption_log (model, timestamp, type) "
                "VALUES ($1, $2, $3)",
                model,
                timestamp,
                type_str,
            )

    async def get_api_consumption_history(self) -> list[tuple[str, float, str]]:
        """Obtiene el historial de consumo de API de las últimas 24 horas."""
        cutoff = time.time() - 86400
        query = (
            "SELECT model, timestamp, type FROM api_consumption_log "
            "WHERE timestamp > $1 ORDER BY timestamp ASC"
        )
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, cutoff)
        return [(row["model"], row["timestamp"], row["type"]) for row in rows]
