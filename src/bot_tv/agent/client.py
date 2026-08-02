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

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


def is_rate_limit_error(e: Exception) -> tuple[bool, float | None]:
    """Determina si un error es debido a Rate Limit (HTTP 429 / Quota / 503 High Demand)
    y extrae el tiempo de espera (Retry-After) si está disponible.
    """
    curr: BaseException | None = e
    while curr is not None:
        msg = str(curr).lower()
        class_name = curr.__class__.__name__.lower()

        if any(
            indicator in msg or indicator in class_name
            for indicator in [
                "429",
                "503",
                "500",
                "502",
                "504",
                "quota",
                "rate_limit",
                "exhausted",
                "resourceexhausted",
                "high demand",
                "overloaded",
                "unavailable",
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
    """Orquesta la interacción con el SDK con rate limiting e historial."""

    def __init__(self, bot: Bot, model: str = DEFAULT_MODEL) -> None:

        if model not in AVAILABLE_MODELS or not AVAILABLE_MODELS[model].enabled:
            model = DEFAULT_MODEL

        self.bot = bot
        self.current_model = model
        self.context_limit = 0  # 0 = Ilimitado
        self._history: list[dict[str, str]] = []
        self.rate_limiter = RateLimiter()
        self.tools = build_agent_tools(bot)
        self._tasks: set[asyncio.Task[None]] = set()

    async def initialize(self) -> None:
        """Carga el modelo activo, el límite de contexto y el consumo histórico."""
        # 1. Cargar modelo activo guardado
        saved_model = await self.bot.settings_repo.get_setting(
            "active_model", self.current_model
        )
        if saved_model in AVAILABLE_MODELS and AVAILABLE_MODELS[saved_model].enabled:
            self.current_model = saved_model
        else:
            self.current_model = DEFAULT_MODEL
            await self.bot.settings_repo.set_setting("active_model", DEFAULT_MODEL)

        # 2. Cargar límite de contexto guardado (0 = ilimitado por defecto)
        saved_limit = await self.bot.settings_repo.get_setting(
            "agent_context_limit", "0"
        )
        try:
            self.context_limit = max(0, int(saved_limit))
        except ValueError:
            self.context_limit = 0

        # 3. Cargar consumo histórico
        history = await self.bot.settings_repo.get_api_consumption_history()
        self.rate_limiter.load_history(history)
        LOGGER.info(
            "TalkAgent inicializado. Modelo: %s | Límite contexto: %s | Consumos: %d",
            self.current_model,
            "Ilimitado" if self.context_limit == 0 else self.context_limit,
            len(history),
        )

    def clear_history(self) -> None:
        """Limpia el historial conversacional en memoria del agente."""
        self._history.clear()

    async def set_context_limit(self, limit: int) -> None:
        """Establece y persiste el límite de contexto conversacional (0 = ilimitado)."""
        self.context_limit = max(0, limit)
        await self.bot.settings_repo.set_setting(
            "agent_context_limit", str(self.context_limit)
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
        task = asyncio.create_task(
            self.bot.settings_repo.set_setting("active_model", model)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return f"Modelo cambiado a: {cfg.display_name} ({model})"

    def get_rpm_status(self) -> RateLimitStatus:
        """Retorna el estado de rate limit del modelo actual."""
        return self.rate_limiter.get_status(self.current_model)

    def get_all_rpm_status(self) -> list[RateLimitStatus]:
        """Retorna el estado de rate limit de todos los modelos."""
        return self.rate_limiter.get_all_status()

    async def chat(self, message: str) -> str:
        """Envía un mensaje al agente resolviendo rate limits e historial."""

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

        broadcaster_info = ""
        channels = await self.bot.get_channels()
        if channels:
            b_names = ", ".join(
                f"@{c['username']} (ID: {c['user_id']})" for c in channels
            )
            broadcaster_info = f"\n- Canal(es) Broadcaster: {b_names}"

        now_local = datetime.datetime.now()
        now_utc = datetime.datetime.now(datetime.UTC)

        # Formatear historial conversacional según el límite configurado
        history_text = ""
        if self._history:
            history_to_use = (
                self._history[-self.context_limit :]
                if self.context_limit > 0
                else self._history
            )
            turns = []
            for turn in history_to_use:
                turns.append(f"Usuario: {turn['question']}")
                turns.append(f"Agente: {turn['response']}")
            history_text = (
                "\n\nHISTORIAL DE CONVERSACIÓN RECIENTE CON EL USUARIO:\n"
                + "\n".join(turns)
            )

        dynamic_instructions = (
            f"{SYSTEM_INSTRUCTIONS}\n\n"
            f"CONTEXTO DEL SISTEMA:\n"
            f"- Local del sistema: {now_local.strftime('%d %b %Y, %H:%M:%S')}\n"
            f"- UTC (Base de datos): {now_utc.strftime('%d %b %Y, %H:%M:%S')}"
            f"{broadcaster_info}"
            f"{history_text}"
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
                await self.bot.settings_repo.log_api_consumption(
                    model_to_use, time.time(), "request"
                )

                text = await response.text()
                if fallback_used:
                    fallback_display = AVAILABLE_MODELS[model_to_use].display_name
                    text = f"[Fallback: {fallback_display}] {text}"

                # Guardar turno en el historial conversacional
                self._history.append({"question": message, "response": text})
                return text

        except Exception as e:
            is_limit, retry_after = is_rate_limit_error(e)
            if is_limit:
                LOGGER.warning(
                    "Error de proveedor/límite para %s (retry_after: %s)",
                    model_to_use,
                    retry_after,
                )
                self.rate_limiter.record_rate_limit_hit(
                    model_to_use, retry_after or 30.0
                )
                await self.bot.settings_repo.log_api_consumption(
                    model_to_use,
                    time.time(),
                    f"hit:{retry_after or 30.0}",
                )

                # Si no se usaba un fallback previamente, intentar uno automáticamente
                if not fallback_used:
                    fallback = self.rate_limiter.find_best_fallback(model_to_use)
                    if fallback:
                        LOGGER.info(
                            "Reintentando consulta con modelo de respaldo: %s",
                            fallback,
                        )
                        fb_config = LocalAgentConfig(
                            system_instructions=dynamic_instructions,
                            tools=self.tools,
                            model=fallback,
                        )
                        try:
                            async with Agent(fb_config) as fb_agent:
                                fb_resp = await fb_agent.chat(message)
                                self.rate_limiter.record_request(fallback)
                                await self.bot.settings_repo.log_api_consumption(
                                    fallback, time.time(), "request"
                                )
                                fb_text = await fb_resp.text()
                                fb_disp = AVAILABLE_MODELS[fallback].display_name
                                return f"[Fallback: {fb_disp}] {fb_text}"
                        except Exception as fb_err:
                            LOGGER.error(
                                "Error también en modelo de respaldo %s: %s",
                                fallback,
                                fb_err,
                            )

                status = self.rate_limiter.get_status(model_to_use)
                display_name = AVAILABLE_MODELS[model_to_use].display_name
                msg_err = (
                    f"[Sobrecarga / Límite] El modelo {display_name} "
                    "no está disponible temporalmente (HTTP 429/503)."
                )

                if status.next_slot_in is not None:
                    msg_err += f" Reintenta en {status.next_slot_in:.0f}s."
                return msg_err

            LOGGER.exception("Error al procesar consulta con el agente de IA: %s", e)
            return (
                f"Lo siento, ocurrió un error al procesar tu solicitud "
                f"con el agente de IA: {e}"
            )
