from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bot_tv.components.followers_component import FollowersComponent
from bot_tv.database.app import (
    get_user_id_by_name,
    is_user_bot,
    set_nickname,
    set_user_bot,
    upsert_user,
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
    """Implementa la lógica de ejecución de los comandos de consola."""

    def __init__(self, bot: Bot, agent: TalkAgent) -> None:
        self.bot = bot
        self.agent = agent

    async def resolve_user(self, comando: str, usuario: str) -> str | None:
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

    async def sync_followers(self) -> None:
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

    async def is_bot(self, args: list[str]) -> None:
        """Marca o desmarca un usuario como bot."""
        if not args:
            LOGGER.warning("is_bot: se requiere un nombre de usuario.")
            return

        usuario = args[0].lower()
        user_id = await self.resolve_user("is_bot", usuario)
        if not user_id:
            return

        es_bot = await is_user_bot(self.bot.app_database, user_id)
        await set_user_bot(self.bot.app_database, user_id, not es_bot)

        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if es_bot:
            LOGGER.info("%s ya no está marcado como bot.", usuario_coloreado)
        else:
            LOGGER.warning("%s fue marcado como bot.", usuario_coloreado)

    async def apodo(self, args: list[str]) -> None:
        """Asigna o elimina el apodo de un usuario."""
        if not args:
            LOGGER.warning("apodo: se requiere un nombre de usuario.")
            return

        usuario = args[0].lower()
        apodo = args[1] if len(args) > 1 else None
        user_id = await self.resolve_user("apodo", usuario)
        if not user_id:
            return

        await set_nickname(self.bot.app_database, user_id, apodo)

        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if apodo:
            LOGGER.info("Apodo de %s cambiado a: %s", usuario_coloreado, apodo)
        else:
            LOGGER.info("Apodo de %s eliminado.", usuario_coloreado)

    def rpm(self, args: list[str]) -> None:
        """Muestra el estado actual del rate limiter para el modelo activo o todos."""
        if args and args[0].lower() == "all":
            statuses = self.agent.get_all_rpm_status()
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
            status = self.agent.get_rpm_status()
            color = VERDE
            if status.is_blocked:
                color = ROJO
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
        from bot_tv.agent.models import AVAILABLE_MODELS

        if not args:
            cfg = AVAILABLE_MODELS.get(self.agent.current_model)
            if cfg:
                display = f"{VERDE}{cfg.display_name}{RESET}"
                print(
                    f"\n{format_timestamp()} Modelo activo: {display} "
                    f"({self.agent.current_model})\n"
                )
        else:
            res = self.agent.switch_model(args[0])
            print(f"\n{format_timestamp()} {res}\n")

    def models(self) -> None:
        """Lista todos los modelos con sus límites y estado de disponibilidad."""
        from bot_tv.agent.models import AVAILABLE_MODELS

        print(f"\n{format_timestamp()} [Modelos Disponibles en AI Studio]")
        for name, cfg in AVAILABLE_MODELS.items():
            status_str = "Habilitado" if cfg.enabled else "Deshabilitado (Límites 0)"
            status_col = VERDE if cfg.enabled else ROJO
            limits_info = (
                f"[RPM: {cfg.rpm_limit}, RPD: {cfg.rpd_limit}]" if cfg.enabled else ""
            )
            print(
                f"  - {cfg.display_name} ({name}): "
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
        await self.bot.close()
