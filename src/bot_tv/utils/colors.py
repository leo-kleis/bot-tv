"""Constantes Rich y utilidades de color para logs y usuarios de Twitch.

Módulo centralizado para el formateo de logs en consola y cálculo determinista
de colores RGB de chatters de Twitch.
"""

from rich.console import Console

# Instancia global de Rich Console para logs del backend
CONSOLE = Console(color_system="truecolor")

# ── Marcado Rich para Colores ──────────────────────────────────────────
RESET = "[/]"
BOLD = "[bold]"
DIM = "[dim]"

# Colores básicos
VERDE = "[green]"
ROJO = "[red]"
AMARILLO = "[yellow]"
CYAN = "[cyan]"

# Colores personalizados (RGB)
MORADO = "[#A970FF]"
NARANJA = "[#FFA31A]"
TIMESTAMP_COLOR = "[#888888]"

# ── Colores por defecto de Twitch ───────────────────────────────────
# Twitch asigna estos colores a los usuarios que no tienen uno propio.
# La lista es la misma que usa el chat oficial de Twitch.
TWITCH_DEFAULT_COLORS: list[tuple[int, int, int]] = [
    (255, 0, 0),  # Red
    (0, 0, 255),  # Blue
    (0, 128, 0),  # Green
    (178, 34, 34),  # FireBrick
    (255, 127, 80),  # Coral
    (154, 205, 50),  # YellowGreen
    (255, 69, 0),  # OrangeRed
    (46, 139, 87),  # SeaGreen
    (218, 165, 32),  # GoldenRod
    (210, 105, 30),  # Chocolate
    (95, 158, 160),  # CadetBlue
    (30, 144, 255),  # DodgerBlue
    (255, 105, 180),  # HotPink
    (138, 43, 226),  # BlueViolet
    (0, 255, 127),  # SpringGreen
]


# ── Funciones utilitarias ───────────────────────────────────────────


def get_rgb_from_hex(hex_color: str | None) -> tuple[int, int, int] | None:
    """Convierte un color hex a una tupla RGB (r, g, b).

    Soporta formatos: '#RRGGBB', '0xRRGGBB', 'RRGGBB'.
    Si el color es None o inválido, devuelve None.
    """
    if not hex_color:
        return None
    hex_color = hex_color.removeprefix("#").removeprefix("0x")
    if len(hex_color) != 6:
        return None
    try:
        return (
            int(hex_color[:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:], 16),
        )
    except ValueError:
        return None


def get_chatter_rgb(hex_color: str | None, username: str) -> tuple[int, int, int]:
    """Obtiene el color RGB de un chatter de Twitch.

    Si el usuario tiene un color personalizado (hex), lo convierte.
    Si no, se le asigna uno por defecto de forma determinista
    (igual que el chat oficial de Twitch).
    """
    if hex_color:
        rgb = get_rgb_from_hex(hex_color)
        if rgb:
            return rgb
    # Determinista: sumar el valor de cada carácter y sacar módulo
    indice = sum(ord(c) for c in username) % len(TWITCH_DEFAULT_COLORS)
    return TWITCH_DEFAULT_COLORS[indice]
