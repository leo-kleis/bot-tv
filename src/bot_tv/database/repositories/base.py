from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

import asyncpg

LOGGER = logging.getLogger(__name__)

_LIKE_SPECIAL_RE = re.compile(r"([%_\\])")
T = TypeVar("T")


def escape_like(term: str) -> str:
    """Escapa caracteres comodín para consultas ILIKE ... ESCAPE '\\'."""
    return _LIKE_SPECIAL_RE.sub(r"\\\1", term)


def to_utc_datetime(val: datetime | str | None) -> datetime | None:
    """Convierte cadenas ISO o datetimes en objetos datetime UTC conscientes de zona."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=UTC) if val.tzinfo is None else val.astimezone(UTC)
    cleaned = val.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    dt = datetime.fromisoformat(cleaned)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_iso_str(val: datetime | str | None) -> str | None:
    """Normaliza objetos datetime o cadenas a formato ISO string."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return val


class BaseRepository:
    """Clase base para todos los repositorios de acceso a datos."""

    def __init__(self, db: asyncpg.Pool) -> None:
        self._db = db

    async def _with_retry(
        self,
        op_fn: Callable[[asyncpg.Connection], Awaitable[T]],
        context_label: str = "operación DB",
    ) -> T:
        """Ejecuta una operación DB con reintento ante desconexión transitoria."""
        for attempt in range(2):
            try:
                async with self._db.acquire() as conn:
                    return await op_fn(conn)
            except (
                asyncpg.ConnectionDoesNotExistError,
                asyncpg.InterfaceError,
                OSError,
            ) as e:
                if attempt == 0:
                    LOGGER.warning(
                        "Conexión perdida en %s (%s). Reintentando...",
                        context_label,
                        e,
                    )
                    await asyncio.sleep(0.15)
                    continue
                raise
        raise RuntimeError(f"Fallo inesperado en _with_retry ({context_label})")
