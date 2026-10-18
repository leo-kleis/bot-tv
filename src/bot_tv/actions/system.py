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
    """Dispara la creación de un clip vía el ClipComponent y espera el resultado."""
    from bot_tv.components.clip_component import ClipComponent
    from bot_tv.events import ClipCreatedEvent as _ClipEvent

    # pyrefly: ignore [missing-attribute]
    component = bot._components.get("ClipComponent")
    if not isinstance(component, ClipComponent):
        LOGGER.error("ClipComponent no encontrado.")
        return "Componente ClipComponent no disponible."

    loop = asyncio.get_running_loop()
    future: asyncio.Future[_ClipEvent | str] = loop.create_future()

    async def on_clip(event: _ClipEvent) -> None:
        if not future.done():
            future.set_result(event)

    bot.event_bus.subscribe(_ClipEvent, on_clip)

    try:
        await component.hacer_clip(raise_on_error=True)
        result = await asyncio.wait_for(future, timeout=15)
    except TimeoutError:
        result = "Timeout: el clip tardó demasiado."
    except Exception as e:
        msg = str(e) or "Fallo al crear el clip en Twitch"
        result = f"Error al crear el clip: {msg}"
    finally:
        bot.event_bus.unsubscribe(_ClipEvent, on_clip)

    return result
