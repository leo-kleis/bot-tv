from __future__ import annotations

import asyncpg


class BaseRepository:
    """Clase base para todos los repositorios de acceso a datos."""

    def __init__(self, db: asyncpg.Pool) -> None:
        self._db = db
