from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_DIR = BASE_DIR / "db"

# Configuración del servidor WebSocket
CAPTION_HOST: str = os.getenv("CAPTION_HOST", "127.0.0.1")
CAPTION_PORT: int = int(os.getenv("CAPTION_PORT", "9000"))

# Configuración de Whisper
CAPTION_MODEL: str = os.getenv("CAPTION_MODEL", "small")
CAPTION_LANGUAGE: str = os.getenv("CAPTION_LANGUAGE", "es")

# Dispositivo de audio (None para el predeterminado, o el índice entero del dispositivo)
_device_env = os.getenv("CAPTION_DEVICE")
CAPTION_DEVICE: int | None = int(_device_env) if _device_env is not None else None

# Parámetros de audio
SAMPLE_RATE: int = 16000
CHANNELS: int = 1
# Bloque de procesamiento de audio en segundos (ej: 0.5s chunks para procesar en stream)
CHUNK_DURATION_SEC: float = 0.5
CHUNK_SIZE: int = int(SAMPLE_RATE * CHUNK_DURATION_SEC)

# Prompt inicial de Whisper para guiar el vocabulario y modismos chilenos
CAPTION_INITIAL_PROMPT: str = (
    "Hablamos en español de Chile, usando modismos chilenos: "
    "weón, wea, cachai, altiro, bacán, fome, pololo, polola, "
    "carrete, yapo, sipo, nopo, pega, luca, cuático, chanta, "
    "pucha, guata, tuto, poto, caña, flaite, de pana, al lote, "
    "engrupido."
)
