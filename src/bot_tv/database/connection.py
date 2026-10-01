from __future__ import annotations

import asyncpg

from bot_tv.utils.env import DATABASE_URL, DIRECT_URL


async def create_pg_pool(*, direct: bool = True) -> asyncpg.Pool:
    """Crea y retorna el pool de conexiones para PostgreSQL.

    Usa DIRECT_URL por defecto para conectar de forma directa sin pasar por
    poolers transaccionales (como PgBouncer), ya que asyncpg gestiona su propio
    pool y requiere soporte nativo de prepared statements.
    """
    url = DIRECT_URL if direct else DATABASE_URL
    return await asyncpg.create_pool(
        url,
        min_size=2,
        max_size=10,
        statement_cache_size=0,
        command_timeout=30,
    )
