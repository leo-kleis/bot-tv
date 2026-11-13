from __future__ import annotations

import base64
import functools
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from bot_tv.utils.env import CLIENT_SECRET, ENCRYPTION_KEY

LOGGER = logging.getLogger(__name__)

_KEY_LENGTH = 32
_HKDF_SALT = b"bot-tv-token-encryption-hkdf-salt-v1"
_HKDF_INFO = b"bot-tv-oauth-fernet-v1"
_PBKDF2_SALT = b"bot-tv-token-encryption-salt-v1"
_PBKDF2_ITERATIONS = 600_000


def _derive_hkdf_fernet(secret: str) -> Fernet:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    key = base64.urlsafe_b64encode(hkdf.derive(secret.encode()))
    return Fernet(key)


def _derive_legacy_fernets(secret: str) -> list[Fernet]:
    secret_bytes = secret.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=_PBKDF2_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    pbkdf2_key = base64.urlsafe_b64encode(kdf.derive(secret_bytes))
    sha256_key = base64.urlsafe_b64encode(hashlib.sha256(secret_bytes).digest())
    return [Fernet(pbkdf2_key), Fernet(sha256_key)]


@functools.lru_cache(maxsize=1)
def _get_fernet_bundle() -> tuple[Fernet, MultiFernet]:
    """Construye y cachea el Fernet primario y el MultiFernet con respaldos legacy."""
    secret = CLIENT_SECRET.strip()
    configured_key = ENCRYPTION_KEY.strip()

    primary: Fernet | None = None
    if configured_key:
        try:
            primary = Fernet(configured_key.encode())
        except ValueError, TypeError:
            LOGGER.warning(
                "ENCRYPTION_KEY no es una clave Fernet válida; "
                "se usará una clave derivada de TWITCH_CLIENT_SECRET."
            )

    if primary is not None:
        fernets: list[Fernet] = [primary]
        if secret:
            # Conservar claves derivadas previas para rotar tokens existentes
            fernets.append(_derive_hkdf_fernet(secret))
            fernets.extend(_derive_legacy_fernets(secret))
        return primary, MultiFernet(fernets)

    if not secret:
        raise RuntimeError("TWITCH_CLIENT_SECRET no está configurado en el entorno.")

    primary = _derive_hkdf_fernet(secret)
    return primary, MultiFernet([primary, *_derive_legacy_fernets(secret)])


def get_fernet() -> MultiFernet:
    """Retorna el MultiFernet cacheado con clave primaria y respaldos legacy."""
    return _get_fernet_bundle()[1]


def encrypt_token(token: str) -> str:
    """Encripta un token en texto plano usando la clave Fernet primaria."""
    return get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Desencripta un token cifrado aceptando clave primaria o respaldos legacy."""
    return get_fernet().decrypt(encrypted_token.encode()).decode()


def decrypt_token_with_rotation(encrypted_token: str) -> tuple[str, str | None]:
    """Desencripta un token y retorna nuevo ciphertext si usó una clave legacy."""
    primary, multi = _get_fernet_bundle()
    token_bytes = encrypted_token.encode()
    try:
        plaintext = primary.decrypt(token_bytes).decode()
    except InvalidToken:
        plaintext = multi.decrypt(token_bytes).decode()
        rotated = multi.rotate(token_bytes).decode()
        return plaintext, rotated
    return plaintext, None
