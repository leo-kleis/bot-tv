from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterable
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from bot_tv.components.followers_component import FollowersComponent
from bot_tv.database.app import (
    get_user_id_by_name,
    is_user_bot,
    set_nickname,
    set_user_bot,
    upsert_user,
)
from bot_tv.utils.colors import AMARILLO, RESET

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class BotCompleter(Completer):
    """Autocompletado contextual para la consola del bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # prompt_toolkit usa get_completions_async para REPL asíncrono
        return []

    async def get_completions_async(
        self, document: Document, complete_event: CompleteEvent
    ) -> AsyncGenerator[Completion]:
        text_before = document.text_before_cursor
        words_before = text_before.split()
        word_before = document.get_word_before_cursor()

        # Posición 1: Comandos
        if len(words_before) == 0 or (
            len(words_before) == 1 and not text_before.endswith(" ")
        ):
            commands_list = ["sync_followers", "is_bot", "apodo", "help", "exit"]
            for cmd in commands_list:
                if cmd.startswith(word_before):
                    yield Completion(cmd, start_position=-len(word_before))

        # Posición 2: Argumento de usuario (para is_bot y apodo)
        elif len(words_before) == 1 or (
            len(words_before) == 2 and not text_before.endswith(" ")
        ):
            cmd = words_before[0].lower()
            if cmd in ("is_bot", "apodo"):
                try:
                    async with self.bot.app_database.acquire() as conn:
                        rows = await conn.fetchall("SELECT username FROM users")
                    usernames = [row["username"] for row in rows]
                    for username in usernames:
                        if username.lower().startswith(word_before.lower()):
                            yield Completion(username, start_position=-len(word_before))
                except Exception:
                    pass


class AdminConsole:
    """Consola administrativa REPL interactiva."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.session = PromptSession(completer=BotCompleter(bot))

    async def run(self) -> None:
        """Inicia el loop REPL asíncrono una vez que el bot esté listo."""
        try:
            # Esperar a que el bot esté completamente conectado
            await self.bot.wait_for("bot_fully_connected")
        except Exception:
            await asyncio.sleep(2)

        LOGGER.info(
            "Consola administrativa iniciada. Escribe 'help' para ver comandos."
        )

        while True:
            try:
                # Leer entrada del usuario
                text = await self.session.prompt_async("bot-tv> ")
                text = text.strip()
                if not text:
                    continue

                parts = text.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd == "exit":
                    await self._cmd_exit()
                    break
                elif cmd == "help":
                    self._cmd_help()
                elif cmd == "sync_followers":
                    await self._cmd_sync_followers()
                elif cmd == "is_bot":
                    if not args:
                        LOGGER.warning("is_bot: se requiere un nombre de usuario.")
                        continue
                    await self._cmd_is_bot(args[0])
                elif cmd == "apodo":
                    if not args:
                        LOGGER.warning("apodo: se requiere un nombre de usuario.")
                        continue
                    usuario = args[0]
                    apodo = args[1] if len(args) > 1 else None
                    await self._cmd_apodo(usuario, apodo)
                else:
                    print(
                        f"Comando desconocido: '{cmd}'. "
                        "Escribe 'help' para ver la lista."
                    )
            except KeyboardInterrupt, EOFError:
                await self._cmd_exit()
                break
            except Exception as e:
                LOGGER.exception("Error al procesar comando en consola: %s", e)

    async def _resolve_user(self, comando: str, usuario: str) -> str | None:
        """Busca el user_id del usuario en la DB local o en Twitch y lo registra."""
        user_id = await get_user_id_by_name(self.bot.app_database, usuario)
        if user_id:
            return user_id

        LOGGER.info(
            "%s: usuario '%s%s%s' no existe en la base de datos. Buscando en Twitch...",
            comando,
            AMARILLO,
            usuario,
            RESET,
        )
        try:
            twitch_user = await self.bot.fetch_user(login=usuario)
            if not twitch_user:
                LOGGER.warning(
                    "%s: usuario '%s%s%s' no encontrado en Twitch.",
                    comando,
                    AMARILLO,
                    usuario,
                    RESET,
                )
                return None

            user_id = twitch_user.id
            await upsert_user(
                self.bot.app_database,
                user_id,
                twitch_user.name or usuario,
                twitch_user.display_name,
            )
            return user_id
        except Exception:
            LOGGER.exception("Error al buscar usuario en Twitch.")
            return None

    async def _cmd_sync_followers(self) -> None:
        """Sincroniza seguidores de todos los canales."""
        channels = await self.bot.get_channels()
        # pyrefly: ignore [missing-attribute]
        component = self.bot._components.get("FollowersComponent")
        if not isinstance(component, FollowersComponent):
            LOGGER.error("Componente FollowersComponent no encontrado o inválido.")
            return

        for channel in channels:
            LOGGER.info("Sincronizando seguidores para %s...", channel["username"])
            try:
                await component.check_and_sync(channel["user_id"])
            except Exception:
                LOGGER.exception(
                    "Error al sincronizar seguidores de %s", channel["username"]
                )

    async def _cmd_is_bot(self, usuario: str) -> None:
        """Marca o desmarca un usuario como bot."""
        usuario = usuario.lower()
        user_id = await self._resolve_user("is_bot", usuario)
        if not user_id:
            return

        es_bot = await is_user_bot(self.bot.app_database, user_id)
        await set_user_bot(self.bot.app_database, user_id, not es_bot)

        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if es_bot:
            LOGGER.info("%s ya no está marcado como bot.", usuario_coloreado)
        else:
            LOGGER.warning("%s fue marcado como bot.", usuario_coloreado)

    async def _cmd_apodo(self, usuario: str, apodo: str | None) -> None:
        """Asigna o elimina el apodo de un usuario."""
        usuario = usuario.lower()
        user_id = await self._resolve_user("apodo", usuario)
        if not user_id:
            return

        await set_nickname(self.bot.app_database, user_id, apodo)

        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if apodo:
            LOGGER.info("Apodo de %s cambiado a: %s", usuario_coloreado, apodo)
        else:
            LOGGER.info("Apodo de %s eliminado.", usuario_coloreado)

    def _cmd_help(self) -> None:
        """Muestra los comandos disponibles."""
        print("Comandos disponibles:")
        print(
            "  sync_followers            - Sincroniza seguidores de todos los canales"
        )
        print("  is_bot <usuario>          - Marca/desmarca un usuario como bot")
        print("  apodo <usuario> [apodo]   - Asigna o elimina el apodo de un usuario")
        print("  help                      - Muestra este mensaje de ayuda")
        print("  exit                      - Cierra el bot de forma limpia")

    async def _cmd_exit(self) -> None:
        """Cierra el bot limpiamente."""
        LOGGER.info("Apagando el bot de forma limpia...")
        await self.bot.close()
