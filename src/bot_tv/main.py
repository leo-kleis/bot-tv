import asyncio
import logging
import sys

import asqlite
from prompt_toolkit.patch_stdout import patch_stdout

from bot_tv.bot import Bot
from bot_tv.console import AdminConsole
from bot_tv.database.app import APP_DB_PATH, setup_app_database
from bot_tv.database.tokens import DB_PATH, setup_token_database
from bot_tv.utils.env import DB_DIR
from bot_tv.utils.logger import setup_logging

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
                    "Ejecutá primero: uv run bot-setup"
                )
                sys.exit(1)

            LOGGER.info("Tokens cargados: %d", len(tokens))
            with patch_stdout(raw=True):
                async with Bot(token_database=tdb, app_database=adb, subs=subs) as bot:
                    for pair in tokens:
                        await bot.add_token(*pair)

                    console = AdminConsole(bot)
                    console_task = asyncio.create_task(console.run())

                    await bot.start(load_tokens=False)
                    await console_task

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando el bot...")
    except RuntimeError as e:
        if "Unable to associate shards with Conduit" in str(e):
            LOGGER.error(
                "Error de conexión con Twitch (EventSub Conduit). "
                "Esto suele ser un problema temporal de red o latencia. "
                "Por favor, reintentá iniciar el bot en unos instantes."
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
