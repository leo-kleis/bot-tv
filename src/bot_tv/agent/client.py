from __future__ import annotations

import asyncio
import datetime
import logging
import re
import time
from typing import TYPE_CHECKING, Final

from google.antigravity import Agent, LocalAgentConfig

from bot_tv.agent.models import AVAILABLE_MODELS, DEFAULT_MODEL
from bot_tv.agent.prompts import SYSTEM_INSTRUCTIONS
from bot_tv.agent.rate_limiter import RateLimiter, RateLimitStatus
from bot_tv.agent.tools import build_agent_tools
from bot_tv.agent.tools._helpers import sanitize_untrusted_text

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

_MAX_HISTORY_TURNS: Final[int] = 50
# Límite de turnos de conversación en memoria incluidos como contexto al
# inicializar una sesión del agente (0 = usar hasta _MAX_HISTORY_TURNS).
# Este parámetro se configura directamente aquí en código (sin persistencia en BD).
AGENT_CONTEXT_LIMIT: Final[int] = 0
_DEFAULT_RETRY_AFTER_SECONDS: Final[float] = 30.0
_RATE_LIMIT_INDICATORS: Final[tuple[str, ...]] = (
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
)
_RETRY_ATTRS: Final[tuple[str, ...]] = ("retry_after", "retry_delay")


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
            for indicator in _RATE_LIMIT_INDICATORS
        ):
            for attr in _RETRY_ATTRS:
                val = getattr(curr, attr, None)
                if val is not None:
                    try:
                        return True, float(val)
                    except ValueError, TypeError:
                        LOGGER.debug("Valor inválido en atributo %s=%r", attr, val)

            headers = getattr(curr, "headers", None)
            if isinstance(headers, dict):
                for k, v in headers.items():
                    if str(k).lower() == "retry-after":
                        try:
                            return True, float(v)
                        except ValueError, TypeError:
                            LOGGER.debug(
                                "Cabecera retry-after inválida: %r",
                                v,
                            )

            match = re.search(r"retry(?:\s+after)?\s*(\d+(?:\.\d+)?)", msg)
            if match:
                return True, float(match.group(1))

            return True, None

        curr = curr.__cause__ or curr.__context__

    return False, None


class TalkAgent:
    """Orquesta la interacción con el SDK con rate limiting, caché e historial."""

    def __init__(self, bot: Bot, model: str = DEFAULT_MODEL) -> None:
        if model not in AVAILABLE_MODELS or not AVAILABLE_MODELS[model].enabled:
            model = DEFAULT_MODEL

        self.bot = bot
        self.current_model = model
        self.context_limit: int = min(max(0, AGENT_CONTEXT_LIMIT), _MAX_HISTORY_TURNS)
        self._history: list[dict[str, str]] = []
        self._chat_lock = asyncio.Lock()
        self.rate_limiter = RateLimiter()
        self.tools = build_agent_tools(bot)
        self._tasks: set[asyncio.Task[None]] = set()

        # Estado de caché del cliente Agent para reutilizar el proceso localharness.
        self._cached_agent: Agent | None = None
        self._cached_model: str | None = None
        self._cached_base_instructions: str | None = None
        self._cached_epoch: int = -1
        self._cached_turn_count: int = 0
        self._session_epoch: int = 0

    async def initialize(self) -> None:
        """Carga el modelo activo y el consumo histórico."""
        saved_model = await self.bot.settings_repo.get_setting(
            "active_model", self.current_model
        )
        if saved_model in AVAILABLE_MODELS and AVAILABLE_MODELS[saved_model].enabled:
            self.current_model = saved_model
        else:
            self.current_model = DEFAULT_MODEL
            await self.bot.settings_repo.set_setting("active_model", DEFAULT_MODEL)

        history = await self.bot.settings_repo.get_api_consumption_history()
        self.rate_limiter.load_history(history)
        LOGGER.info(
            "TalkAgent inicializado. Modelo: %s | Límite contexto: %s | Consumos: %d",
            self.current_model,
            (
                f"Hasta {_MAX_HISTORY_TURNS} turnos"
                if self.context_limit == 0
                else self.context_limit
            ),
            len(history),
        )

    async def _close_cached_agent(self) -> None:
        """Cierra de forma segura el Agent en caché y limpia su referencia."""
        agent = self._cached_agent
        self._cached_agent = None
        self._cached_model = None
        self._cached_base_instructions = None
        self._cached_epoch = -1
        self._cached_turn_count = 0

        if agent is not None:
            try:
                await agent.__aexit__(None, None, None)
            except Exception as exc:
                LOGGER.warning("Error al cerrar sesión cacheada del agente: %s", exc)

    async def close(self) -> None:
        """Cierra la sesión activa del agente y cancela tareas pendientes."""
        async with self._chat_lock:
            await self._close_cached_agent()

        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def clear_history(self) -> None:
        """Limpia el historial conversacional en memoria e invalida la sesión activa."""
        self._history.clear()
        self._session_epoch += 1

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

    def _build_base_instructions(self, channels: list[dict[str, str]]) -> str:
        """Construye las instrucciones estables del sistema para cachear el Agent."""
        broadcaster_info = ""
        if channels:
            b_names = ", ".join(
                f"@{c['username']} (ID: {c['user_id']})" for c in channels
            )
            broadcaster_info = (
                f"\n\nCONTEXTO DEL CANAL:\n- Canal(es) Broadcaster: {b_names}"
            )
        return f"{SYSTEM_INSTRUCTIONS}{broadcaster_info}"

    def _format_history_text(self) -> tuple[str, int]:
        """Formatea el historial reciente para inicializar un Agent nuevo."""
        if not self._history:
            return "", 0

        history_to_use = (
            self._history[-self.context_limit :]
            if self.context_limit > 0
            else self._history
        )
        turns: list[str] = []
        for turn in history_to_use:
            safe_q = sanitize_untrusted_text(turn["question"])
            safe_r = sanitize_untrusted_text(turn["response"])
            turns.append(f"Usuario: {safe_q}")
            turns.append(f"Agente: {safe_r}")

        history_text = (
            "\n\nHISTORIAL DE CONVERSACIÓN RECIENTE CON EL USUARIO "
            "(solo como referencia de contexto previo):\n"
            "<conversation_history>\n" + "\n".join(turns) + "\n</conversation_history>"
        )
        return history_text, len(history_to_use)

    def _build_turn_prompt(self, message: str) -> str:
        """Adjunta marcas temporales del turno al mensaje sin invalidar el Agent."""
        now_local = datetime.datetime.now()
        now_utc = datetime.datetime.now(datetime.UTC)
        return (
            "CONTEXTO TEMPORAL ACTUAL:\n"
            f"- Local del sistema: {now_local.strftime('%d %b %Y, %H:%M:%S')}\n"
            f"- UTC (Base de datos): {now_utc.strftime('%d %b %Y, %H:%M:%S')}\n\n"
            f"{message}"
        )

    async def _get_or_create_agent(
        self, model_name: str, base_instructions: str
    ) -> Agent:
        """Reutiliza el Agent activo si configuración/modelo no cambiaron."""
        context_exceeded = (
            self.context_limit > 0 and self._cached_turn_count > self.context_limit
        )
        can_reuse = (
            self._cached_agent is not None
            and self._cached_agent.is_started
            and self._cached_model == model_name
            and self._cached_base_instructions == base_instructions
            and self._cached_epoch == self._session_epoch
            and not context_exceeded
        )
        if can_reuse and self._cached_agent is not None:
            return self._cached_agent

        await self._close_cached_agent()

        history_text, seeded_turns = self._format_history_text()
        full_instructions = (
            f"{base_instructions}{history_text}" if history_text else base_instructions
        )

        config = LocalAgentConfig(
            system_instructions=full_instructions,
            tools=self.tools,
            model=model_name,
        )
        agent = Agent(config)
        await agent.__aenter__()

        self._cached_agent = agent
        self._cached_model = model_name
        self._cached_base_instructions = base_instructions
        self._cached_epoch = self._session_epoch
        self._cached_turn_count = seeded_turns
        return agent

    async def _execute_chat_turn(
        self,
        model_name: str,
        base_instructions: str,
        message: str,
    ) -> str:
        """Ejecuta un turno contra el Agent (cacheado o nuevo) y actualiza memoria."""
        turn_epoch = self._session_epoch
        agent = await self._get_or_create_agent(model_name, base_instructions)
        turn_prompt = self._build_turn_prompt(message)

        try:
            response = await agent.chat(turn_prompt)
            clean_text = await response.text()
        except Exception:
            await self._close_cached_agent()
            raise

        self.rate_limiter.record_request(model_name)
        if self._session_epoch == turn_epoch:
            self._cached_turn_count += 1
            self._history.append({"question": message, "response": clean_text})
            self._history = self._history[-_MAX_HISTORY_TURNS:]
        else:
            # Si el usuario limpió el historial en paralelo, invalidar sesión usada.
            await self._close_cached_agent()
        return clean_text

    async def _persist_consumption_logs(
        self, pending_logs: list[tuple[str, float, str]]
    ) -> None:
        """Persiste los registros de consumo en DB fuera de _chat_lock."""
        for model_name, timestamp, log_type in pending_logs:
            try:
                await self.bot.settings_repo.log_api_consumption(
                    model_name, timestamp, log_type
                )
            except Exception as exc:
                LOGGER.warning(
                    "No se pudo registrar consumo de API (%s, %s): %s",
                    model_name,
                    log_type,
                    exc,
                )

    async def chat(self, message: str) -> str:
        """Envía un mensaje al agente resolviendo rate limits e historial."""
        channels = await self.bot.get_channels()
        base_instructions = self._build_base_instructions(channels)

        pending_logs: list[tuple[str, float, str]] = []
        response_text: str | None = None
        used_model = self.current_model
        fallback_used = False
        rate_limit_msg: str | None = None
        unexpected_error_msg: str | None = None

        async with self._chat_lock:
            model_to_use = self.current_model

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

            used_model = model_to_use
            try:
                response_text = await self._execute_chat_turn(
                    model_to_use, base_instructions, message
                )
                pending_logs.append((model_to_use, time.time(), "request"))
            except Exception as e:
                is_limit, retry_after = is_rate_limit_error(e)
                if is_limit:
                    wait_seconds = retry_after or _DEFAULT_RETRY_AFTER_SECONDS
                    LOGGER.warning(
                        "Error de proveedor/límite para %s (retry_after: %s)",
                        model_to_use,
                        retry_after,
                    )
                    self.rate_limiter.record_rate_limit_hit(model_to_use, wait_seconds)
                    pending_logs.append(
                        (model_to_use, time.time(), f"hit:{wait_seconds}")
                    )

                    if not fallback_used:
                        fallback = self.rate_limiter.find_best_fallback(model_to_use)
                        if fallback:
                            LOGGER.info(
                                "Reintentando consulta con modelo de respaldo: %s",
                                fallback,
                            )
                            try:
                                response_text = await self._execute_chat_turn(
                                    fallback, base_instructions, message
                                )
                                used_model = fallback
                                fallback_used = True
                                pending_logs.append((fallback, time.time(), "request"))
                            except Exception as fb_err:
                                LOGGER.error(
                                    "Error también en modelo de respaldo %s: %s",
                                    fallback,
                                    fb_err,
                                )
                                fb_is_limit, fb_retry = is_rate_limit_error(fb_err)
                                if fb_is_limit:
                                    fb_wait = fb_retry or _DEFAULT_RETRY_AFTER_SECONDS
                                    self.rate_limiter.record_rate_limit_hit(
                                        fallback, fb_wait
                                    )
                                    pending_logs.append(
                                        (fallback, time.time(), f"hit:{fb_wait}")
                                    )

                    if response_text is None:
                        status = self.rate_limiter.get_status(model_to_use)
                        display_name = AVAILABLE_MODELS[model_to_use].display_name
                        msg_err = (
                            f"[Sobrecarga / Límite] El modelo {display_name} "
                            "no está disponible temporalmente (HTTP 429/503)."
                        )
                        if status.next_slot_in is not None:
                            msg_err += f" Reintenta en {status.next_slot_in:.0f}s."
                        rate_limit_msg = msg_err
                else:
                    LOGGER.exception(
                        "Error al procesar consulta con el agente de IA: %s", e
                    )
                    unexpected_error_msg = (
                        f"Lo siento, ocurrió un error al procesar tu solicitud "
                        f"con el agente de IA: {e}"
                    )

        if pending_logs:
            await self._persist_consumption_logs(pending_logs)

        if response_text is not None:
            if fallback_used:
                fallback_display = AVAILABLE_MODELS[used_model].display_name
                return f"[Fallback: {fallback_display}] {response_text}"
            return response_text
        if rate_limit_msg is not None:
            return rate_limit_msg
        return unexpected_error_msg or ""
