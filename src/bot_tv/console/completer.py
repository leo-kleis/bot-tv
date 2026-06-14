from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from typing import TYPE_CHECKING

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from bot_tv.bot import Bot


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
            commands_list = [
                "sync_followers",
                "is_bot",
                "apodo",
                "talk",
                "rpm",
                "model",
                "models",
                "help",
                "exit",
            ]
            for cmd in commands_list:
                if cmd.startswith(word_before):
                    yield Completion(cmd, start_position=-len(word_before))

        # Posición 2: Argumentos (usuarios o nombres de modelo)
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
            elif cmd == "model":
                from bot_tv.agent.models import get_enabled_models

                for model_name in get_enabled_models():
                    if model_name.startswith(word_before):
                        yield Completion(model_name, start_position=-len(word_before))
