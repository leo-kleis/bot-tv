import os

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
# ID del Conduit de EventSub (se muestra en el log la primera vez que arranca el bot)
CONDUIT_ID: str = os.getenv("CONDUIT_ID", "")
