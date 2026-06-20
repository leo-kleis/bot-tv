from __future__ import annotations

import asqlite

from bot_tv.utils.env import DB_DIR

# Rutas absolutas a los archivos de base de datos
APP_DB_PATH = DB_DIR / "app.db"
TOKEN_DB_PATH = DB_DIR / "tokens.db"


def create_app_db_pool() -> asqlite.PoolContextManager:
    """Crea y retorna el pool de conexiones para la base de datos de la app."""
    return asqlite.create_pool(str(APP_DB_PATH))


def create_token_db_pool() -> asqlite.PoolContextManager:
    """Crea y retorna el pool de conexiones para la base de datos de tokens."""
    return asqlite.create_pool(str(TOKEN_DB_PATH))
