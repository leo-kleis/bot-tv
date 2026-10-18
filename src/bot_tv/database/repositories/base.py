from __future__ import annotations

import re
from datetime import UTC, datetime

import asyncpg

_LIKE_SPECIAL_RE = re.compile(r"([%_\\])")


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
