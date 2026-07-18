import base64
import hashlib

from cryptography.fernet import Fernet

from bot_tv.utils.env import CLIENT_SECRET


def get_fernet() -> Fernet:
    """Deriva una clave Fernet determinista de 32 bytes a partir del CLIENT_SECRET."""
    key = base64.urlsafe_b64encode(hashlib.sha256(CLIENT_SECRET.encode()).digest())
    return Fernet(key)
