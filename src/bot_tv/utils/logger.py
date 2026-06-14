import logging

from bot_tv.utils.colors import BOLD, RESET, TIMESTAMP_COLOR

# Colores para los niveles
LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[34m",  # Azul
    logging.INFO: "\033[32m",  # Verde
    logging.WARNING: "\033[33m",  # Amarillo
    logging.ERROR: "\033[31m",  # Rojo
    logging.CRITICAL: f"{BOLD}\033[31m",  # Rojo brillante
}

# Color por defecto para el nombre del módulo (cyan)
NAME_COLOR = "\033[36m"

# Colores específicos por módulo
MODULE_COLORS: dict[str, str] = {
    "components.followers_component": "\033[38;2;198;120;221m",  # #C678DD
}


class ColorFormatter(logging.Formatter):
    """Formateador con colores para la terminal."""

    def format(self, record: logging.LogRecord) -> str:
        level_color = LEVEL_COLORS.get(record.levelno, RESET)
        level = f"{level_color}{record.levelname:<8}{RESET}"
        name_color = MODULE_COLORS.get(record.name, NAME_COLOR)
        name = f"{name_color}{record.name}{RESET}"
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage()

        return f"{TIMESTAMP_COLOR}[{timestamp}]{RESET} {level} {name}: {message}"


class ConduitWarningFilter(logging.Filter):
    """Silencia el warning de 'conduit_id' en twitchio.client."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "twitchio.client"
            and record.levelno == logging.WARNING
            and 'No "conduit_id" was passed' in record.getMessage()
        )


class EventSubReconnectFilter(logging.Filter):
    """Simplifica el warning de reconexión de conduits a un mensaje legible."""

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name == "twitchio.eventsub.websockets"
            and "needs to close unexpectedly" in str(record.msg)
        ):
            record.msg = "Reconectando canal de EventSub/Chat automáticamente."
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logging con colores personalizados."""
    formatter = ColorFormatter(datefmt="%d/%m/%y %H:%M:%S")

    from prompt_toolkit.patch_stdout import StdoutProxy

    handler = logging.StreamHandler(StdoutProxy(raw=True))
    handler.setFormatter(formatter)

    # Configurar el logger raíz en WARNING para silenciar logs del SDK/terceros
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.addHandler(handler)

    # Configurar el logger específico de la aplicación en INFO
    app_logger = logging.getLogger("bot_tv")
    app_logger.setLevel(level)
    app_logger.propagate = True

    # Silenciar explícitamente otros loggers de Google SDK
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google.antigravity").setLevel(logging.WARNING)

    # Filtros específicos para logs de twitchio
    logging.getLogger("twitchio.client").addFilter(ConduitWarningFilter())
    logging.getLogger("twitchio.eventsub.websockets").addFilter(
        EventSubReconnectFilter()
    )
