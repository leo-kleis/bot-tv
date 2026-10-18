import base64
import functools
import hashlib

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from bot_tv.utils.env import CLIENT_SECRET

_PBKDF2_SALT = b"bot-tv-token-encryption-salt-v1"
_PBKDF2_ITERATIONS = 600_000


@functools.lru_cache(maxsize=1)
def get_fernet() -> MultiFernet:
    """Deriva un MultiFernet con clave primaria PBKDF2HMAC y respaldo SHA-256."""
    if not CLIENT_SECRET or not CLIENT_SECRET.strip():
        raise RuntimeError("TWITCH_CLIENT_SECRET no está configurado en el entorno.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PBKDF2_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    kdf_key = base64.urlsafe_b64encode(kdf.derive(CLIENT_SECRET.encode()))
    legacy_key = base64.urlsafe_b64encode(
        hashlib.sha256(CLIENT_SECRET.encode()).digest()
    )
    return MultiFernet([Fernet(kdf_key), Fernet(legacy_key)])
