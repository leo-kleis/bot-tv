import logging

from bot_tv.colors import BOLD, RESET, TIMESTAMP_COLOR

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
    "bot_tv.components.followers_component": "\033[38;2;198;120;221m",  # #C678DD
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


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logging con colores personalizados."""
    formatter = ColorFormatter(datefmt="%d/%m/%y %H:%M:%S")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Configurar el logger raíz para que todos los loggers hereden esta config
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
