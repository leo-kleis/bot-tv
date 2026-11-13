from __future__ import annotations

import logging

import asyncpg

from bot_tv.utils.env import DATABASE_URL, DIRECT_URL

LOGGER = logging.getLogger(__name__)

_POOL_MIN_SIZE = 2
_POOL_MAX_SIZE = 10
_POOL_MAX_QUERIES = 50_000
_DIRECT_STATEMENT_CACHE_SIZE = 100
_POOLED_STATEMENT_CACHE_SIZE = 0
_CONNECT_TIMEOUT_SECONDS = 10.0
_COMMAND_TIMEOUT_SECONDS = 30.0
_MAX_INACTIVE_LIFETIME_SECONDS = 300.0


class DatabaseConnectionError(Exception):
    """Fallo no recuperable al conectar o inicializar el pool de PostgreSQL."""


async def create_pg_pool(*, direct: bool = True) -> asyncpg.Pool:
    """Crea y retorna el pool de conexiones para PostgreSQL.

    Usa DIRECT_URL por defecto para conectar de forma directa sin pasar por
    poolers transaccionales (como PgBouncer), ya que asyncpg gestiona su propio
    pool y requiere soporte nativo de prepared statements.
    """
    url = (DIRECT_URL if direct else DATABASE_URL).strip()
    if not url:
        env_var = "DIRECT_URL" if direct else "DATABASE_URL"
        raise DatabaseConnectionError(
            f"La variable {env_var} está vacía o no configurada."
        )

    statement_cache_size = (
        _DIRECT_STATEMENT_CACHE_SIZE if direct else _POOLED_STATEMENT_CACHE_SIZE
    )
    pool = await asyncpg.create_pool(
        url,
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
        max_queries=_POOL_MAX_QUERIES,
        statement_cache_size=statement_cache_size,
        timeout=_CONNECT_TIMEOUT_SECONDS,
        command_timeout=_COMMAND_TIMEOUT_SECONDS,
        max_inactive_connection_lifetime=_MAX_INACTIVE_LIFETIME_SECONDS,
    )
    if pool is None:
        raise DatabaseConnectionError(
            "asyncpg.create_pool devolvió None al inicializar el pool."
        )
    return pool


async def init_pg_pool(*, direct: bool = True) -> asyncpg.Pool:
    """Inicializa el pool de conexiones diagnosticando la causa exacta de fallos.

    Traduce las excepciones de bajo nivel (driver, red, credenciales) en un
    DatabaseConnectionError con mensaje claro y accionable para los runners.
    """
    try:
        return await create_pg_pool(direct=direct)
    except DatabaseConnectionError:
        raise
    except asyncpg.InvalidPasswordError as exc:
        raise DatabaseConnectionError(
            "Error de autenticación: usuario o contraseña incorrectos "
            "en la variable de base de datos."
        ) from exc
    except asyncpg.InvalidCatalogNameError as exc:
        raise DatabaseConnectionError(
            "La base de datos especificada en la URL de conexión no existe."
        ) from exc
    except TimeoutError as exc:
        raise DatabaseConnectionError(
            "Tiempo de espera agotado al conectar con el servidor PostgreSQL."
        ) from exc
    except OSError as exc:
        raise DatabaseConnectionError(
            "No se pudo conectar al servidor PostgreSQL "
            f"(servidor apagado o puerto inaccesible): {exc}"
        ) from exc
    except (asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
        raise DatabaseConnectionError(
            f"Error de protocolo o configuración de PostgreSQL: {exc}"
        ) from exc
    except ValueError as exc:
        raise DatabaseConnectionError(
            f"Formato de URL de base de datos inválido: {exc}"
        ) from exc
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Fallo inesperado al inicializar el pool de PostgreSQL: {exc}"
        ) from exc
