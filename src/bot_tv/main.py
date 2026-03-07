import asyncio
import logging
import sys

import asqlite
import twitchio

from bot_tv.bot import Bot
from bot_tv.database import DB_DIR, DB_PATH, setup_database

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación."""
    twitchio.utils.setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with asqlite.create_pool(str(DB_PATH)) as tdb:
            tokens, subs = await setup_database(tdb)

            if not tokens:
                LOGGER.error(
                    "No se encontraron tokens en la base de datos. "
                    "Ejecutá primero: poetry run bot-setup"
                )
                sys.exit(1)

            LOGGER.info("Tokens cargados: %d", len(tokens))
            async with Bot(token_database=tdb, subs=subs) as bot:
                for pair in tokens:
                    await bot.add_token(*pair)
                await bot.start(load_tokens=False)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando el bot...")


if __name__ == "__main__":
    main()
