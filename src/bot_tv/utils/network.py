from __future__ import annotations

import logging

import requests

LOGGER = logging.getLogger(__name__)


def check_twitch_connection(timeout: float = 4.0) -> bool:
    """Verifica si la API de Twitch (id.twitch.tv) es accesible."""
    try:
        # Hacemos una petición GET rápida a la URL de validación
        requests.get("https://id.twitch.tv/oauth2/validate", timeout=timeout)
        return True
    except Exception as e:
        LOGGER.error(
            "Fallo al conectar con Twitch en id.twitch.tv. Detalle: %s",
            e,
        )
        return False
