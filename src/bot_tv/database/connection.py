from __future__ import annotations

import asyncpg

from bot_tv.utils.env import DATABASE_URL, DIRECT_URL


async def create_pg_pool(*, direct: bool = False) -> asyncpg.Pool:
    """Crea y retorna el pool de conexiones para PostgreSQL.

    Usa el connection string directo cuando direct=True (migraciones).
    """
    url = DIRECT_URL if direct else DATABASE_URL
    return await asyncpg.create_pool(url, min_size=2, max_size=10)
