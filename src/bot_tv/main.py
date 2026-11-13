"""Punto de entrada unificado de bot-tv: bot + servidor web en el mismo asyncio loop.

El terminal muestra los logs del backend (TwitchIO, base de datos y servidor web).
Toda la visualización, administración y control se realiza desde la aplicación web.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
from pathlib import Path

import uvicorn

from bot_tv.agent import TalkAgent
from bot_tv.bot import Bot
from bot_tv.database import (
    DatabaseConnectionError,
    TokenRepository,
    init_pg_pool,
)
from bot_tv.event_bus import EventBus
from bot_tv.utils.env import (
    APP_ENV,
    GEMINI_MODEL,
    IDLE_SHUTDOWN_SECONDS,
    IS_DEV,
    MAX_WS_CLIENTS,
    WEB_HOST,
    WEB_PORT,
)
from bot_tv.utils.logger import setup_logging
from bot_tv.utils.network import (
    check_twitch_connection,
    close_http_client,
    get_port_process_info,
    init_http_client,
    is_port_in_use,
)
from bot_tv.web.server import create_app

LOGGER = logging.getLogger(__name__)
_DEFAULT_FORWARDED_ALLOW_IPS = "127.0.0.1,::1"


def main() -> None:
    """Punto de entrada principal de la aplicación web."""
    setup_logging(level=logging.INFO)

    async def runner() -> None:
        LOGGER.info(
            "Iniciando bot-tv (v1.0.0-beta.1) | Entorno: %s (max_ws=%d, idle=%ds)",
            APP_ENV.upper(),
            MAX_WS_CLIENTS,
            IDLE_SHUTDOWN_SECONDS,
        )
        try:
            LOGGER.info("Conectando a la base de datos PostgreSQL...")
            try:
                pool = await init_pg_pool()
            except DatabaseConnectionError as exc:
                LOGGER.critical(
                    "No se pudo conectar a la base de datos PostgreSQL: %s",
                    exc,
                )
                sys.exit(1)
            LOGGER.info("Conexión con PostgreSQL establecida.")

            try:
                init_http_client()
                LOGGER.info("Cargando tokens de autenticación y suscripciones...")
                token_repo = TokenRepository(pool)
                tokens, subs = await token_repo.load_tokens_and_subscriptions()

                if not tokens:
                    LOGGER.error(
                        "No se encontraron tokens en la base de datos. "
                        "Ejecutá primero: uv run bot-setup"
                    )
                    sys.exit(1)

                LOGGER.info("Tokens cargados: %d", len(tokens))

                LOGGER.info("Verificando disponibilidad del puerto web %d...", WEB_PORT)
                if await asyncio.to_thread(is_port_in_use, WEB_PORT, WEB_HOST):
                    info = await asyncio.to_thread(get_port_process_info, WEB_PORT)
                    if info:
                        pid, process_name = info
                        LOGGER.critical(
                            "El puerto %d está ocupado por el proceso '%s' (PID: %d). "
                            "Cerrá ese proceso antes de ejecutar bot-tv.",
                            WEB_PORT,
                            process_name,
                            pid,
                        )
                    else:
                        LOGGER.critical(
                            "El puerto %d ya está en uso por otro proceso o instancia. "
                            "Cerrá la instancia anterior o libera el puerto antes "
                            "de ejecutar bot-tv.",
                            WEB_PORT,
                        )
                    sys.exit(1)

                LOGGER.info("Verificando conexión con la API de Twitch...")
                if not await check_twitch_connection():
                    LOGGER.critical(
                        "No se pudo establecer conexión con Twitch (id.twitch.tv). "
                        "Por favor, verifica tu conexión a internet o la "
                        "configuración de DNS/red. "
                        "El inicio del bot ha sido cancelado para evitar "
                        "congelamientos."
                    )
                    sys.exit(1)

                LOGGER.info("Inicializando cliente de Twitch y agente de IA...")
                event_bus = EventBus()

                async with Bot(
                    database=pool,
                    subs=subs,
                    event_bus=event_bus,
                ) as bot:
                    await bot.load_initial_tokens(tokens)

                    agent = TalkAgent(bot, model=GEMINI_MODEL)
                    await agent.initialize()
                    bot.agent = agent

                    try:
                        app = create_app(bot, agent, event_bus)

                        ssl_keyfile = None
                        ssl_certfile = None
                        certs_dir = Path("certs")
                        # En desarrollo local usamos certs/ para la PWA en LAN;
                        # en producción delegamos TLS al proxy (Tailscale / Cloud).
                        if IS_DEV and certs_dir.exists():
                            key_files = list(certs_dir.glob("*-key.pem"))
                            cert_files = [
                                f
                                for f in certs_dir.glob("*.pem")
                                if not f.name.endswith("-key.pem")
                            ]
                            if key_files and cert_files:
                                ssl_keyfile = str(key_files[0])
                                ssl_certfile = str(cert_files[0])
                                LOGGER.info(
                                    "Configurando HTTPS local (DEV) con certs: %s y %s",
                                    ssl_certfile,
                                    ssl_keyfile,
                                )

                        forwarded_allow_ips = (
                            os.getenv("FORWARDED_ALLOW_IPS", "").strip()
                            or _DEFAULT_FORWARDED_ALLOW_IPS
                        )
                        config = uvicorn.Config(
                            app,
                            host=WEB_HOST,
                            port=WEB_PORT,
                            log_level="info",
                            log_config=None,
                            loop="none",
                            ssl_keyfile=ssl_keyfile,
                            ssl_certfile=ssl_certfile,
                            timeout_graceful_shutdown=2,
                            proxy_headers=True,
                            forwarded_allow_ips=forwarded_allow_ips,
                        )
                        server = uvicorn.Server(config)
                        app.state.server = server
                        app.state.ws_manager.set_shutdown_callback(
                            lambda: setattr(server, "should_exit", True)
                        )

                        protocol = "https" if ssl_certfile else "http"
                        LOGGER.info(
                            "Dashboard [%s] en %s://%s:%d",
                            APP_ENV.upper(),
                            protocol,
                            WEB_HOST,
                            WEB_PORT,
                        )

                        bot_task = asyncio.create_task(
                            bot.start(load_tokens=False, save_tokens=False)
                        )
                        server_task = asyncio.create_task(server.serve())

                        _done, pending = await asyncio.wait(
                            [bot_task, server_task],
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        if pending:
                            _done_after, pending = await asyncio.wait(
                                pending,
                                timeout=5.0,
                            )

                        for task in pending:
                            task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await task
                    finally:
                        await agent.close()
            finally:
                await close_http_client()
                await pool.close()
        finally:
            import gc

            gc.collect()
            await asyncio.sleep(0.25)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando bot-tv...")
    except RuntimeError as e:
        if "Unable to associate shards with Conduit" in str(e):
            LOGGER.error(
                "Error de conexión con Twitch (EventSub Conduit). "
                "Esto suele ser temporal. Reintentá en unos instantes."
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
