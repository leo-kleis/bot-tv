"""Acciones de ciclo de vida del bot y creación de clips."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot_tv.bot import Bot
    from bot_tv.events import ClipCreatedEvent

LOGGER = logging.getLogger(__name__)


async def action_exit(bot: Bot) -> None:
    """Cierra el bot limpiamente."""
    await bot.close()


async def action_create_clip(bot: Bot) -> ClipCreatedEvent | str:
    """Dispara la creación de un clip vía el ClipComponent y retorna el resultado."""
    from bot_tv.components.clip_component import ClipComponent

    # pyrefly: ignore [missing-attribute]
    component = bot._components.get("ClipComponent")
    if not isinstance(component, ClipComponent):
        LOGGER.error("ClipComponent no encontrado.")
        return "Componente ClipComponent no disponible."

    try:
        event = await asyncio.wait_for(
            component.hacer_clip(raise_on_error=True), timeout=15
        )
        if event is None:
            return "Error al crear el clip: no se obtuvo respuesta de Twitch."
        return event
    except TimeoutError:
        return "Timeout: el clip tardó demasiado."
    except Exception as e:
        msg = str(e) or "Fallo al crear el clip en Twitch"
        return f"Error al crear el clip: {msg}"
