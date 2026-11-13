from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

import asyncpg

LOGGER = logging.getLogger(__name__)

_LIKE_SPECIAL_RE = re.compile(r"([%_\\])")
_DEFAULT_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 0.15
_TRANSIENT_DB_ERRORS: tuple[type[BaseException], ...] = (
    asyncpg.PostgresConnectionError,
    asyncpg.TransactionRollbackError,
    asyncpg.TooManyConnectionsError,
    asyncpg.CannotConnectNowError,
    asyncpg.AdminShutdownError,
    asyncpg.CrashShutdownError,
    asyncpg.IdleSessionTimeoutError,
    asyncpg.IdleInTransactionSessionTimeoutError,
    OSError,
)
T = TypeVar("T")


def _is_transient_db_error(exc: BaseException) -> bool:
    """Indica si una excepción proviene de desconexión, pool o deadlock."""
    if isinstance(exc, _TRANSIENT_DB_ERRORS):
        return True
    # Distinguir conexión cerrada de errores de datos o pool en cierre (InterfaceError).
    return (
        type(exc) is asyncpg.InterfaceError
        and "connection is closed" in str(exc).lower()
    )


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
        *,
        max_attempts: int = _DEFAULT_RETRY_ATTEMPTS,
    ) -> T:
        """Ejecuta una operación DB con reintentos ante errores transitorios."""
        attempts = max(1, max_attempts)
        for attempt in range(attempts):
            try:
                async with self._db.acquire() as conn:
                    return await op_fn(conn)
            except Exception as exc:
                if not _is_transient_db_error(exc) or attempt >= attempts - 1:
                    raise
                delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                LOGGER.warning(
                    "Error transitorio en %s (intento %d/%d: %s). "
                    "Reintentando en %.2fs...",
                    context_label,
                    attempt + 1,
                    attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        raise RuntimeError(f"Fallo inesperado en _with_retry ({context_label})")

    async def _with_transaction(
        self,
        op_fn: Callable[[asyncpg.Connection], Awaitable[T]],
        context_label: str = "transacción DB",
        *,
        max_attempts: int = _DEFAULT_RETRY_ATTEMPTS,
    ) -> T:
        """Ejecuta múltiples sentencias de forma atómica con reintento completo."""

        async def _run(conn: asyncpg.Connection) -> T:
            async with conn.transaction():
                return await op_fn(conn)

        return await self._with_retry(
            _run,
            context_label=context_label,
            max_attempts=max_attempts,
        )

    async def _fetch(
        self,
        query: str,
        *args: Any,
        context_label: str = "consulta DB",
    ) -> list[asyncpg.Record]:
        """Ejecuta una consulta SELECT multi-fila protegida por reintentos."""

        async def _op(conn: asyncpg.Connection) -> list[asyncpg.Record]:
            return await conn.fetch(query, *args)

        return await self._with_retry(_op, context_label=context_label)

    async def _fetchrow(
        self,
        query: str,
        *args: Any,
        context_label: str = "consulta DB",
    ) -> asyncpg.Record | None:
        """Ejecuta una consulta SELECT de una fila protegida por reintentos."""

        async def _op(conn: asyncpg.Connection) -> asyncpg.Record | None:
            return await conn.fetchrow(query, *args)

        return await self._with_retry(_op, context_label=context_label)

    async def _execute(
        self,
        query: str,
        *args: Any,
        context_label: str = "escritura DB",
    ) -> str:
        """Ejecuta una sentencia SQL de escritura protegida por reintentos."""

        async def _op(conn: asyncpg.Connection) -> str:
            return await conn.execute(query, *args)

        return await self._with_retry(_op, context_label=context_label)
