import asyncio
import logging
import sys

from prompt_toolkit.patch_stdout import patch_stdout

from bot_tv.bot import Bot
from bot_tv.console import AdminConsole
from bot_tv.consumers.terminal import TerminalConsumer
from bot_tv.database import (
    TokenRepository,
    create_app_db_pool,
    create_token_db_pool,
    run_app_migrations,
    run_token_migrations,
)
from bot_tv.event_bus import EventBus
from bot_tv.utils.env import DB_DIR
from bot_tv.utils.logger import setup_logging

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación (terminal con Rich + REPL)."""
    setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        try:
            async with (
                create_token_db_pool() as tdb,
                create_app_db_pool() as adb,
            ):
                await run_token_migrations(tdb)
                await run_app_migrations(adb)

                token_repo = TokenRepository(tdb)
                tokens, subs = await token_repo.load_tokens_and_subscriptions()

                if not tokens:
                    LOGGER.error(
                        "No se encontraron tokens en la base de datos. "
                        "Ejecutá primero: uv run bot-setup"
                    )
                    sys.exit(1)

                LOGGER.info("Tokens cargados: %d", len(tokens))

                event_bus = EventBus()
                # Consumer de terminal: reproduce el output Rich de los componentes
                TerminalConsumer(event_bus)

                with patch_stdout(raw=True):
                    async with Bot(
                        token_database=tdb,
                        app_database=adb,
                        subs=subs,
                        event_bus=event_bus,
                    ) as bot:
                        for pair in tokens:
                            await bot.add_token(*pair)

                        console = AdminConsole(bot)
                        console_task = asyncio.create_task(console.run())

                        await bot.start(load_tokens=False)
                        await console_task
        finally:
            import gc

            gc.collect()
            await asyncio.sleep(0.25)

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
