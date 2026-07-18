from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import keyboard
import twitchio
from twitchio.ext import commands

from bot_tv.events import ClipCreatedEvent
from bot_tv.utils.colors import AMARILLO, RESET, ROJO, VERDE

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class ClipComponent(commands.Component):
    """Componente que escucha la tecla F6 y crea un clip como broadcaster."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._loop = asyncio.get_running_loop()
        self._clip_en_progreso = False

        # Registrar el F6
        self._register_hotkey()

    def _register_hotkey(self) -> None:
        """Registra el hotkey global."""
        try:
            keyboard.add_hotkey("F6", self._on_f6_pressed)
            LOGGER.info(
                "Atajo de teclado %sF6 registrado%s para crear clips.", VERDE, RESET
            )
        except Exception as e:
            LOGGER.error("No se pudo registrar F6: %s", e)

    def _on_f6_pressed(self) -> None:
        """Llamado de forma síncrona por 'keyboard' al presionar F6."""
        if self._clip_en_progreso:
            return  # Evitar múltiples presiones accidentales

        self._clip_en_progreso = True
        # Delegar al loop asíncrono sin bloquear el hilo de keyboard
        asyncio.run_coroutine_threadsafe(self.hacer_clip(), self._loop)

    async def hacer_clip(self, raise_on_error: bool = False) -> None:
        """Llama a la API de Twitch para crear un clip y lo envía al chat."""
        try:
            LOGGER.info("%sCreando clip...%s", AMARILLO, RESET)

            # Verificar si el stream está online
            from bot_tv.components.stream_component import StreamComponent

            stream_comp = self.bot._components.get("StreamComponent")
            if (
                isinstance(stream_comp, StreamComponent)
                and not stream_comp._stream_online
            ):
                LOGGER.error(
                    "%sEl canal no está en vivo. No se puede crear un clip.%s",
                    ROJO,
                    RESET,
                )
                if raise_on_error:
                    raise ValueError("El canal no está en vivo.")
                return

            # 1. Buscar a nuestro propio broadcaster (dueño del canal a clipear)
            # Acorde a bot.py, el canal es aquel cuyo user_id != bot_id
            async with self.bot.database.acquire() as connection:
                row = await connection.fetchrow(
                    "SELECT user_id, username, token FROM tokens WHERE user_id != $1",
                    self.bot.bot_id,
                )

            if not row:
                LOGGER.error(
                    "%sNo se encontró la cuenta del CANAL para hacer el clip.%s",
                    ROJO,
                    RESET,
                )
                if raise_on_error:
                    raise ValueError(
                        "No se encontró la cuenta del canal para hacer el clip."
                    )
                return

            broadcaster_id = row["user_id"]
            broadcaster_name = row["username"]

            # 2. Obtener el partial_user para usarlo en el llamado
            canal_user = twitchio.PartialUser(
                id=broadcaster_id,
                name=broadcaster_name,
                http=self.bot._http,
            )

            # 3. Llamar a create_clip
            # token_for recibe el user_id del broadcaster para que TwitchIO
            # busque su token almacenado internamente (requiere scope clips:edit).
            clip = await canal_user.create_clip(token_for=broadcaster_id)

            if not clip:
                LOGGER.error("%sTwitch no devolvió ningún clip válido.%s", ROJO, RESET)
                if raise_on_error:
                    raise ValueError("Twitch no devolvió ningún clip válido.")
                return

            # 4. Extraemos la URL (por defecto, Twitch y TwitchIO devuelven edit_url)
            edit_url = getattr(clip, "edit_url", None)
            clip_id = getattr(clip, "id", "Desconocido")

            if isinstance(clip, dict) and not edit_url:
                edit_url = clip.get("edit_url")
                clip_id = clip.get("id", clip_id)

            url_final = edit_url if edit_url else f"https://clips.twitch.tv/{clip_id}"

            LOGGER.info("%s¡Clip creado con éxito!%s URL: %s", VERDE, RESET, url_final)

            await self.bot.event_bus.emit(
                ClipCreatedEvent(
                    timestamp=datetime.now().isoformat(),
                    url=url_final,
                    broadcaster_name=broadcaster_name,
                )
            )

            # 5. Mandar el link al chat (lo habla el Bot)
            msg = (
                f"¡Nuevo clip generado en vivo! El creador lo editará aquí: {url_final}"
            )
            await canal_user.send_message(
                message=msg,
                sender=self.bot.bot_id,
                token_for=self.bot.bot_id,
            )

        except twitchio.HTTPException as e:
            LOGGER.error(
                "%sFallo al crear el clip en Twitch. Revisa la consola.%s", ROJO, RESET
            )
            if e.status in (401, 403, 400):
                LOGGER.error("Error de la API (%s)", e.status)
            if raise_on_error:
                raise
        except Exception as e:
            LOGGER.exception("Error inesperado al crear el clip: %s", e)
            if raise_on_error:
                raise
        finally:
            self._clip_en_progreso = False
