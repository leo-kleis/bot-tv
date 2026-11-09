import os

from dotenv import load_dotenv

load_dotenv()

# ==========================================
# Entorno de Ejecución (development | production)
# ==========================================
_raw_env = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION: bool = _raw_env in {"prod", "production"}
IS_DEV: bool = not IS_PRODUCTION
APP_ENV: str = "production" if IS_PRODUCTION else "development"

# ==========================================
# Credenciales de Twitch API e IRC
# ==========================================
CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")
CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
BOT_ID: str = os.getenv("BOT_ID", "")
OWNER_ID: str = os.getenv("OWNER_ID", "")
IRC_TOKEN: str = os.getenv("IRC_TOKEN", "")

# ==========================================
# Base de Datos PostgreSQL (Prisma Postgres / Prisma Console)
# ==========================================
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
DIRECT_URL: str = os.getenv("DIRECT_URL", DATABASE_URL)

# ==========================================
# Google Gemini AI
# ==========================================
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# ==========================================
# Servidor Web, Reglas y Límites por Entorno
# ==========================================
WEB_HOST: str = os.getenv("WEB_HOST") or os.getenv("HOST", "0.0.0.0")  # noqa: S104
WEB_PORT: int = int(os.getenv("WEB_PORT") or os.getenv("PORT", "8080"))
WEB_ACCESS_TOKEN: str = os.getenv("WEB_ACCESS_TOKEN", "")

# Orígenes adicionales permitidos (ej. dominio Tailscale https://bot-tv.tailnet.ts.net)
CORS_ORIGINS: frozenset[str] = frozenset(
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
)

# Límite máximo de conexiones WebSocket simultáneas:
# - En development (local): 20 conexiones para pruebas multidispositivo
# - En production (nube/único usuario): 3 conexiones por defecto
_default_max_ws = "3" if IS_PRODUCTION else "20"
MAX_WS_CLIENTS: int = max(1, int(os.getenv("MAX_WS_CLIENTS", _default_max_ws)))

# Tiempo de inactividad sin usuarios conectados (0 clientes WebSocket) antes de
# apagar automáticamente el proceso:
# - En development (local): 0 (desactivado, siempre encendido mientras desarrollas)
# - En production (nube bajo demanda): 300 segundos (5 min) por defecto
_default_idle_sec = "300" if IS_PRODUCTION else "0"
IDLE_SHUTDOWN_SECONDS: int = max(
    0, int(os.getenv("IDLE_SHUTDOWN_SECONDS", _default_idle_sec))
)
