import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Usa variables de entorno o un archivo .env — nunca valores fijos en el código
# CLIENT ID del Twitch Dev Console
CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")
# CLIENT SECRET del Twitch Dev Console
CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
# ID de la cuenta bot
BOT_ID: str = os.getenv("BOT_ID", "")
# Tu ID de usuario personal
OWNER_ID: str = os.getenv("OWNER_ID", "")
# Token exclusivo para conexión de chat IRC (https://twitchtokengenerator.com/)
IRC_TOKEN: str = os.getenv("IRC_TOKEN", "")

# ---------

# Directorio de bases de datos (relativo al CWD o absoluto)
DB_DIR: Path = Path(os.getenv("BOT_TV_DB_DIR", "db")).resolve()
# API Key para Antigravity SDK
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Modelo por defecto del Antigravity SDK
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
