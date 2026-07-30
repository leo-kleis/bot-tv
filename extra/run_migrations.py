"""Script utilitario para crear las tablas en PostgreSQL."""

import asyncio
import sys

sys.path.insert(0, "src")

from bot_tv.database import create_pg_pool


async def main() -> None:
    print("Verificando tablas en PostgreSQL...")
    pool = await create_pg_pool()
    async with pool.acquire() as conn:
        query = (
            "SELECT tablename FROM pg_tables"
            " WHERE schemaname = 'public' ORDER BY tablename"
        )
        tables = await conn.fetch(query)
        print(f"Tablas creadas ({len(tables)}):")
        for t in tables:
            print(f"  - {t['tablename']}")
    await pool.close()
    print("Listo.")


asyncio.run(main())
