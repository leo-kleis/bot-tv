"""Constantes ANSI y utilidades de color/formateo para la terminal.

Módulo centralizado para evitar la duplicación de códigos ANSI
y funciones de color a lo largo del proyecto.
"""

from datetime import datetime

# ── Códigos ANSI ────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Colores básicos
VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[33m"
CYAN = "\033[96m"

# Colores personalizados (RGB)
TIMESTAMP_COLOR = "\033[38;2;94;79;247m"  # #5E4FF7
MORADO = "\033[38;2;169;112;255m"  # #A970FF (morado Twitch)
NARANJA = "\033[38;2;255;163;26m"  # #FFA31A

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


def format_colored_name(
    display_name: str,
    nickname: str | None,
    r: int,
    g: int,
    b: int,
) -> str:
    """Formatea un nombre de usuario con color ANSI.

    Si tiene nickname: muestra "Nickname {display_name}" donde
    el nickname va en color brillante y el display_name en color oscuro.
    Si no: muestra "display_name" en color brillante.
    """
    color_ansi = f"\033[38;2;{r};{g};{b}m"
    if nickname:
        dark_r, dark_g, dark_b = int(r * 0.5), int(g * 0.5), int(b * 0.5)
        dark_ansi = f"\033[38;2;{dark_r};{dark_g};{dark_b}m"
        return f"{color_ansi}{nickname}{dark_ansi} {{{display_name}}}{RESET}"
    return f"{color_ansi}{display_name}{RESET}"


def format_timestamp() -> str:
    """Devuelve un timestamp formateado con color: [HH:MM:SS]."""
    hora = datetime.now().strftime("%H:%M:%S")
    return f"{TIMESTAMP_COLOR}[{hora}]{RESET}"
