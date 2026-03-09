import asyncio
import logging
import sys

import asqlite

from bot_tv.app_database import APP_DB_PATH, setup_app_database
from bot_tv.bot import Bot
from bot_tv.logger import setup_logging
from bot_tv.token_database import DB_DIR, DB_PATH, setup_token_database

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación."""
    setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with (
            asqlite.create_pool(str(DB_PATH)) as tdb,
            asqlite.create_pool(str(APP_DB_PATH)) as adb,
        ):
            tokens, subs = await setup_token_database(tdb)
            await setup_app_database(adb)

            if not tokens:
                LOGGER.error(
                    "No se encontraron tokens en la base de datos. "
                    "Ejecutá primero: poetry run bot-setup"
                )
                sys.exit(1)

            LOGGER.info("Tokens cargados: %d", len(tokens))
            async with Bot(token_database=tdb, app_database=adb, subs=subs) as bot:
                for pair in tokens:
                    await bot.add_token(*pair)
                await bot.start(load_tokens=False)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando el bot...")


if __name__ == "__main__":
    main()
