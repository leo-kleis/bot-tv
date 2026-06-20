from __future__ import annotations

import asqlite


class BaseRepository:
    """Clase base para todos los repositorios de acceso a datos."""

    def __init__(self, db: asqlite.Pool) -> None:
        self._db = db
