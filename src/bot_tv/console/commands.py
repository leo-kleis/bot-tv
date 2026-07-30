from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_tv.actions.agent import (
    action_get_models,
    action_get_rpm_status,
    action_switch_model,
)
from bot_tv.actions.followers import action_sync_followers
from bot_tv.actions.system import action_exit
from bot_tv.actions.users import (
    action_set_nickname,
    action_toggle_bot,
)
from bot_tv.utils.colors import (
    AMARILLO,
    CONSOLE,
    RESET,
    ROJO,
    VERDE,
    format_timestamp,
)

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot

print = CONSOLE.print

LOGGER = logging.getLogger(__name__)


class AdminCommands:
    """Implementa la lógica de presentación de los comandos de consola.

    Delega la lógica de negocio a actions.py y formatea el resultado con Rich.
    """

    def __init__(self, bot: Bot, agent: TalkAgent) -> None:
        self.bot = bot
        self.agent = agent

    async def sync_followers(self) -> None:
        """Sincroniza seguidores de todos los canales."""
        results = await action_sync_followers(self.bot)
        for result in results:
            if result.ok:
                LOGGER.info("Seguidores de %s sincronizados.", result.channel)
            else:
                LOGGER.error(
                    "Error al sincronizar %s: %s", result.channel, result.error
                )

    async def is_bot(self, args: list[str]) -> None:
        """Marca o desmarca un usuario como bot."""
        if not args:
            LOGGER.warning("is_bot: se requiere un nombre de usuario.")
            return

        result = await action_toggle_bot(self.bot, args[0])
        if isinstance(result, str):
            LOGGER.warning("is_bot: %s", result)
            return

        usuario_coloreado = f"{AMARILLO}{result.username}{RESET}"
        if result.is_bot:
            LOGGER.warning("%s fue marcado como bot.", usuario_coloreado)
        else:
            LOGGER.info("%s ya no está marcado como bot.", usuario_coloreado)

    async def apodo(self, args: list[str]) -> None:
        """Asigna o elimina el apodo de un usuario."""
        if not args:
            LOGGER.warning("apodo: se requiere un nombre de usuario.")
            return

        nickname = args[1] if len(args) > 1 else None
        result = await action_set_nickname(self.bot, args[0], nickname)
        if isinstance(result, str):
            LOGGER.warning("apodo: %s", result)
            return

        usuario_coloreado = f"{AMARILLO}{result.username}{RESET}"
        if result.nickname:
            LOGGER.info(
                "Apodo de %s cambiado a: %s", usuario_coloreado, result.nickname
            )
        else:
            LOGGER.info("Apodo de %s eliminado.", usuario_coloreado)

    def rpm(self, args: list[str]) -> None:
        """Muestra el estado actual del rate limiter para el modelo activo o todos."""
        show_all = bool(args) and args[0].lower() == "all"
        statuses = action_get_rpm_status(self.agent, show_all)

        if show_all:
            print(f"\n{format_timestamp()} [Estado de RPM por Modelo]")
            print(
                f"  {'Modelo':<25} | {'RPM Usado':<10} | "
                f"{'RPD Usado':<10} | {'Estado':<12}"
            )
            print("  " + "-" * 65)
            for s in statuses:
                color = VERDE
                status_text = "OK"
                if s.is_blocked:
                    color = ROJO
                    status_text = s.blocked_reason or "Bloqueado"
                elif s.rpm_used > 0:
                    color = AMARILLO

                rpm_str = (
                    f"{s.rpm_used}/{s.rpm_limit}" if s.rpm_limit > 0 else "0/0 (N/A)"
                )
                rpd_str = (
                    f"{s.rpd_used}/{s.rpd_limit}" if s.rpd_limit > 0 else "0/0 (N/A)"
                )
                print(
                    f"  {color}{s.display_name:<25}{RESET} | "
                    f"{rpm_str:<10} | {rpd_str:<10} | {color}{status_text}{RESET}"
                )
            print()
        else:
            status = statuses[0]
            color = ROJO if status.is_blocked else VERDE
            print(
                f"\n{format_timestamp()} [RPM] {color}{status.display_name}{RESET} "
                f"({status.model}):"
            )
            print(f"  RPM Usado: {status.rpm_used}/{status.rpm_limit}")
            print(f"  RPD Usado: {status.rpd_used}/{status.rpd_limit}")
            if status.is_blocked:
                print(f"  Estado: {color}BLOQUEADO ({status.blocked_reason}){RESET}")
                if status.next_slot_in is not None:
                    print(f"  Próximo slot en: {status.next_slot_in:.1f}s")
            else:
                print(f"  Estado: {color}OK{RESET}")
            print()

    def model(self, args: list[str]) -> None:
        """Muestra o cambia el modelo activo en runtime."""
        if not args:
            cfg = AVAILABLE_MODELS_MAP.get(self.agent.current_model)
            if cfg:
                display = f"{VERDE}{cfg.display_name}{RESET}"
                print(
                    f"\n{format_timestamp()} Modelo activo: {display} "
                    f"({self.agent.current_model})\n"
                )
        else:
            res = action_switch_model(self.agent, args[0])
            print(f"\n{format_timestamp()} {res}\n")

    def models(self) -> None:
        """Lista todos los modelos con sus límites y estado de disponibilidad."""
        infos = action_get_models()
        print(f"\n{format_timestamp()} [Modelos Disponibles en AI Studio]")
        for info in infos:
            status_str = "Habilitado" if info.enabled else "Deshabilitado (Límites 0)"
            status_col = VERDE if info.enabled else ROJO
            limits_info = (
                f"[RPM: {info.rpm_limit}, RPD: {info.rpd_limit}]"
                if info.enabled
                else ""
            )
            print(
                f"  - {info.display_name} ({info.name}): "
                f"{status_col}{status_str}{RESET} {limits_info}"
            )
        print()

    def help(self) -> None:
        """Muestra los comandos disponibles."""
        print("Comandos disponibles:")
        print(
            "  sync_followers            - Sincroniza seguidores de todos los canales"
        )
        print("  is_bot <usuario>          - Marca/desmarca un usuario como bot")
        print("  apodo <usuario> [apodo]   - Asigna o elimina el apodo de un usuario")
        print("  talk <mensaje>            - Pregunta o interactúa con el asistente IA")
        print(
            "  rpm [all]                 - Muestra el estado del RPM (actual o todos)"
        )
        print(
            "  model [nombre]            - Muestra o cambia el modelo activo en runtime"
        )
        print(
            "  models                    - Lista todos los modelos y su disponibilidad"
        )
        print("  help                      - Muestra este mensaje de ayuda")
        print("  exit                      - Cierra el bot de forma limpia")

    async def exit(self) -> None:
        """Cierra el bot limpiamente."""
        LOGGER.info("Apagando el bot de forma limpia...")
        await action_exit(self.bot)


# Import tardío para evitar import circular (solo usado en model())
from bot_tv.agent.models import AVAILABLE_MODELS as AVAILABLE_MODELS_MAP  # noqa: E402
