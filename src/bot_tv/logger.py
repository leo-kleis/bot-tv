import logging

# Códigos ANSI para colores en terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Colores para los niveles
LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[34m",  # Azul
    logging.INFO: "\033[32m",  # Verde
    logging.WARNING: "\033[33m",  # Amarillo
    logging.ERROR: "\033[31m",  # Rojo
    logging.CRITICAL: "\033[1;31m",  # Rojo brillante
}

# Color para el nombre del módulo (cyan — no se usa en ningún nivel)
NAME_COLOR = "\033[36m"


class ColorFormatter(logging.Formatter):
    """Formateador con colores para la terminal."""

    def format(self, record: logging.LogRecord) -> str:
        level_color = LEVEL_COLORS.get(record.levelno, RESET)
        level = f"{level_color}{record.levelname:<8}{RESET}"
        name = f"{NAME_COLOR}{record.name}{RESET}"
        timestamp = self.formatTime(record, self.datefmt)
        message = record.getMessage()

        return f"{DIM}{timestamp}{RESET} {level} {name}: {message}"


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logging con colores personalizados."""
    formatter = ColorFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Configurar el logger raíz para que todos los loggers hereden esta config
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
