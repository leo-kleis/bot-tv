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

    future: asyncio.Future[_ClipEvent | str] = asyncio.get_event_loop().create_future()

    original_emit = bot.event_bus.emit

    async def capture_and_restore(event: object) -> None:
        if isinstance(event, _ClipEvent) and not future.done():
            future.set_result(event)
        await original_emit(event)

    bot.event_bus.emit = capture_and_restore  # type: ignore[assignment]

    try:
        await component.hacer_clip(raise_on_error=True)
        result = await asyncio.wait_for(future, timeout=15)
    except TimeoutError:
        result = "Timeout: el clip tardó demasiado."
    except Exception as e:
        msg = str(e) or "Fallo al crear el clip en Twitch"
        result = f"Error al crear el clip: {msg}"
    finally:
        bot.event_bus.emit = original_emit  # type: ignore[assignment]

    return result
