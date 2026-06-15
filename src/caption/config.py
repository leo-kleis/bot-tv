from __future__ import annotations

import contextlib
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Rutas del proyecto
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DB_DIR: Path = BASE_DIR / "db"

# Configuración del servidor WebSocket
CAPTION_HOST: str = os.getenv("CAPTION_HOST", "127.0.0.1")

_port_env: str = os.getenv("CAPTION_PORT", "9000")
try:
    CAPTION_PORT: int = int(_port_env)
except ValueError:
    # Si el puerto no es un número válido, usar el puerto por defecto 9000
    CAPTION_PORT = 9000

# Configuración de Whisper
CAPTION_MODEL: str = os.getenv("CAPTION_MODEL", "medium")
CAPTION_LANGUAGE: str = os.getenv("CAPTION_LANGUAGE", "es")

# Dispositivo de audio (None para el predeterminado, o el índice del dispositivo)
_device_env: str | None = os.getenv("CAPTION_DEVICE")
CAPTION_DEVICE: int | None = None
if _device_env is not None:
    with contextlib.suppress(ValueError):
        CAPTION_DEVICE = int(_device_env)

# Parámetros de audio
SAMPLE_RATE: int = 16000
CHANNELS: int = 1
# Bloque de procesamiento de audio en segundos (ej: 0.5s chunks para procesar en stream)
CHUNK_DURATION_SEC: float = 0.5
CHUNK_SIZE: int = int(SAMPLE_RATE * CHUNK_DURATION_SEC)

# Prompt de Whisper estructurado para guiar al habla chilena y modismos
CAPTION_INITIAL_PROMPT: str = (
    "¡Hola! Hablamos en español de Chile. Diálogos cotidianos con modismos y "
    "chilenismos: cachai, weón, weona, altiro, bacán, po, ya po, si po, no po, "
    "fome, pololo, polola, carrete, pega, luca, cuático, chanta, pucha, guata, "
    "tuto, poto, caña, flaite, de pana, al lote, engrupido, la dura, al toque. "
    "Transcripción limpia, natural y respetando las expresiones locales."
)

