from __future__ import annotations

import asyncio
import datetime
import logging
import re
import time
from typing import TYPE_CHECKING

from google.antigravity import Agent, LocalAgentConfig

from bot_tv.agent.models import AVAILABLE_MODELS, DEFAULT_MODEL
from bot_tv.agent.prompts import SYSTEM_INSTRUCTIONS
from bot_tv.agent.rate_limiter import RateLimiter, RateLimitStatus
from bot_tv.agent.tools import build_agent_tools
from bot_tv.database.app import (
    get_api_consumption_history,
    get_setting,
    log_api_consumption,
    set_setting,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def is_rate_limit_error(e: Exception) -> tuple[bool, float | None]:
    """Determina si un error es debido a Rate Limit (HTTP 429 / Quota) y
    extrae el tiempo de espera (Retry-After) si está disponible.
    """
    curr: BaseException | None = e
    while curr is not None:
        msg = str(curr).lower()
        class_name = curr.__class__.__name__.lower()

        if any(
            indicator in msg or indicator in class_name
            for indicator in [
                "429",
                "quota",
                "rate_limit",
                "exhausted",
                "resourceexhausted",
            ]
        ):
            # Buscar Retry-After en atributos comunes
            for attr in ["retry_after", "retry_delay"]:
                val = getattr(curr, attr, None)
                if val is not None:
                    try:
                        return True, float(val)
                    except ValueError, TypeError:
                        pass

            # Buscar en cabeceras HTTP si están presentes
            headers = getattr(curr, "headers", None)
            if isinstance(headers, dict):
                for k, v in headers.items():
                    if k.lower() == "retry-after":
                        try:
                            return True, float(v)
                        except ValueError, TypeError:
                            pass

            # Intentar parsear el mensaje de error por si dice "retry after X seconds"
            match = re.search(r"retry(?:\s+after)?\s*(\d+(?:\.\d+)?)", msg)
            if match:
                return True, float(match.group(1))

            return True, None

        curr = curr.__cause__ or curr.__context__

    return False, None


class TalkAgent:
    """Orquesta la interacción con el SDK con rate limiting persistido."""

    def __init__(self, bot: Bot, model: str = DEFAULT_MODEL) -> None:
        if model not in AVAILABLE_MODELS or not AVAILABLE_MODELS[model].enabled:
            model = DEFAULT_MODEL

        self.bot = bot
        self.current_model = model
        self.rate_limiter = RateLimiter()
        self.tools = build_agent_tools(bot)

    async def initialize(self) -> None:
        """Carga el modelo activo y el consumo histórico desde la base de datos."""
        # 1. Cargar modelo activo guardado
        saved_model = await get_setting(
            self.bot.app_database, "active_model", self.current_model
        )
        if saved_model in AVAILABLE_MODELS and AVAILABLE_MODELS[saved_model].enabled:
            self.current_model = saved_model

        # 2. Cargar consumo histórico
        history = await get_api_consumption_history(self.bot.app_database)
        self.rate_limiter.load_history(history)
        LOGGER.info(
            "TalkAgent inicializado con modelo activo: %s y %d registros de consumo.",
            self.current_model,
            len(history),
        )

    def switch_model(self, model: str) -> str:
        """Cambia el modelo activo persistiendo la selección."""
        if model not in AVAILABLE_MODELS:
            return "Error: Modelo desconocido. Usa 'models' para ver la lista."
        cfg = AVAILABLE_MODELS[model]
        if not cfg.enabled:
            return (
                f"Error: El modelo '{model}' está deshabilitado en el plan free tier."
            )

        self.current_model = model
        # Persistir selección en segundo plano
        asyncio.create_task(set_setting(self.bot.app_database, "active_model", model))
        return f"Modelo cambiado a: {cfg.display_name} ({model})"

    def get_rpm_status(self) -> RateLimitStatus:
        """Retorna el estado de rate limit del modelo actual."""
        return self.rate_limiter.get_status(self.current_model)

    def get_all_rpm_status(self) -> list[RateLimitStatus]:
        """Retorna el estado de rate limit de todos los modelos."""
        return self.rate_limiter.get_all_status()

    async def chat(self, message: str) -> str:
        """Envía un mensaje al agente resolviendo rate limits y fallback."""
        model_to_use = self.current_model
        fallback_used = False

        # Verificar rate limit del modelo activo
        if not self.rate_limiter.can_request(model_to_use):
            fallback = self.rate_limiter.find_best_fallback(model_to_use)
            if fallback is None:
                status = self.rate_limiter.get_status(model_to_use)
                display_name = AVAILABLE_MODELS[model_to_use].display_name
                msg_err = f"[Rate Limit] Límite alcanzado para {display_name}."
                if status.next_slot_in is not None:
                    msg_err += f" Próximo slot libre en {status.next_slot_in:.0f}s."
                return msg_err

            model_to_use = fallback
            fallback_used = True

        now_local = datetime.datetime.now()
        now_utc = datetime.datetime.now(datetime.UTC)
        dynamic_instructions = (
            f"{SYSTEM_INSTRUCTIONS}\n\n"
            f"FECHA Y HORA ACTUAL:\n"
            f"- Local del sistema: {now_local.strftime('%d %b %Y, %H:%M:%S')}\n"
            f"- UTC (Base de datos): {now_utc.strftime('%d %b %Y, %H:%M:%S')}"
        )

        config = LocalAgentConfig(
            system_instructions=dynamic_instructions,
            tools=self.tools,
            model=model_to_use,
        )

        try:
            async with Agent(config) as agent:
                response = await agent.chat(message)

                # Registrar consumo localmente y en base de datos
                self.rate_limiter.record_request(model_to_use)
                await log_api_consumption(
                    self.bot.app_database, model_to_use, time.time(), "request"
                )

                text = await response.text()
                if fallback_used:
                    fallback_display = AVAILABLE_MODELS[model_to_use].display_name
                    text = f"[Fallback: {fallback_display}] {text}"
                return text
        except Exception as e:
            is_limit, retry_after = is_rate_limit_error(e)
            if is_limit:
                LOGGER.warning(
                    "Rate limit hit en ejecución para modelo %s (retry_after: %s)",
                    model_to_use,
                    retry_after,
                )
                # Registrar el bloqueo localmente y en base de datos
                self.rate_limiter.record_rate_limit_hit(model_to_use, retry_after)
                await log_api_consumption(
                    self.bot.app_database,
                    model_to_use,
                    time.time(),
                    f"hit:{retry_after or 60.0}",
                )

                status = self.rate_limiter.get_status(model_to_use)
                msg_err = (
                    f"[Rate Limit] Error 429 (Límite Excedido) al usar "
                    f"{AVAILABLE_MODELS[model_to_use].display_name}."
                )
                if status.next_slot_in is not None:
                    msg_err += f" Bloqueado por {status.next_slot_in:.0f}s."
                return msg_err

            LOGGER.exception("Error al procesar consulta con el agente de IA: %s", e)
            return (
                f"Lo siento, ocurrió un error al procesar tu solicitud "
                f"con el agente de IA: {e}"
            )
