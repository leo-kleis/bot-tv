import asyncio
import logging
import sys

from prompt_toolkit.patch_stdout import patch_stdout

from bot_tv.bot import Bot
from bot_tv.console import AdminConsole
from bot_tv.consumers.terminal import TerminalConsumer
from bot_tv.database import (
    TokenRepository,
    create_pg_pool,
    run_pg_migrations,
)
from bot_tv.event_bus import EventBus
from bot_tv.utils.logger import setup_logging

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación (terminal con Rich + REPL)."""
    setup_logging(level=logging.INFO)

    async def runner() -> None:
        try:
            pool = await create_pg_pool()
            try:
                await run_pg_migrations(pool)

                token_repo = TokenRepository(pool)
                tokens, subs = await token_repo.load_tokens_and_subscriptions()

                if not tokens:
                    LOGGER.error(
                        "No se encontraron tokens en la base de datos. "
                        "Ejecutá primero: uv run bot-setup"
                    )
                    sys.exit(1)

                LOGGER.info("Tokens cargados: %d", len(tokens))

                # Verificar conexión a Twitch
                from bot_tv.utils.network import check_twitch_connection

                LOGGER.info("Verificando conexión con la API de Twitch...")
                if not check_twitch_connection(timeout=4.0):
                    LOGGER.critical(
                        "No se pudo establecer conexión con Twitch (id.twitch.tv). "
                        "Por favor, verifica tu conexión a internet o la "
                        "configuración de DNS/red. "
                        "El inicio del bot ha sido cancelado para evitar "
                        "congelamientos."
                    )
                    sys.exit(1)

                event_bus = EventBus()
                TerminalConsumer(event_bus)

                with patch_stdout(raw=True):
                    async with Bot(
                        database=pool,
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
                await pool.close()
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
