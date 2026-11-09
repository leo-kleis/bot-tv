# Reglas Arquitectónicas y de Mantenibilidad Obligatorias (`v1.0.0-beta.1`)

1. **Arquitectura 100% Web App & PWA**:
   - El proyecto opera exclusivamente a través del servidor web (`Starlette` + `Uvicorn`) y su Dashboard interactivo PWA (`src/bot_tv/main.py`).
   - Queda prohibido reintroducir modos de consola CLI/REPL (`prompt-toolkit`), consumidores de terminal o hooks de teclado de sistema operativo (`keyboard`). Toda acción o atajo (como `F6` para clips) debe gestionarse desde la interfaz web y sus endpoints REST/WebSocket.

2. **Base de Datos Híbrida (Prisma Postgres + `asyncpg`)**:
   - Consultar siempre `docs/database.md` y `prisma/schema.prisma` al interactuar o modificar entidades de la base de datos.
   - El esquema y las migraciones viven exclusivamente en Prisma (`prisma/schema.prisma` y `prisma/migrations/`), conectándose a la base de datos de **Prisma Console (Prisma Postgres)**.
   - En tiempo de ejecución en Python, todas las consultas deben usar `asyncpg` dentro de repositorios que hereden de `BaseRepository` (`src/bot_tv/database/repositories/base.py`) empleando `self._with_retry(...)` para tolerar cortes o cierres de conexiones inactivas.

3. **Estados de Ejecución (`APP_ENV=development` vs `APP_ENV=production`)**:
   - **`development` (por defecto en local)**: Orientado a red local (LAN `0.0.0.0:8080`), habilita certificados locales (`certs/*.pem`) para prueba de PWA en móvil, activa *live-reload* (`watchfiles`), desactiva caché agresiva de JS/CSS y mantiene el proceso encendido permanentemente (`IDLE_SHUTDOWN_SECONDS=0`).
   - **`production` (nube / servidor con Tailscale)**: Activa cabeceras HSTS y cookies seguras, delega TLS al proxy/Tailscale, habilita caché de activos estáticos, restringe el límite de clientes WebSocket (`MAX_WS_CLIENTS=3` para uso personal) y activa el auto-apagado bajo demanda cuando no hay usuarios conectados (`IDLE_SHUTDOWN_SECONDS=300`).

4. **Red Asíncrona y Seguridad de Datos**:
   - Prohibido realizar llamadas HTTP síncronas (`requests`, `urllib.request`) dentro del bucle de eventos asíncrono; utilizar siempre `get_http_client()` (`httpx.AsyncClient` compartido en `src/bot_tv/utils/network.py`).
   - Todo texto externo proveniente del chat o de usuarios de Twitch que se inyecte en herramientas del Agente IA (`src/bot_tv/agent/tools/`) debe pasar por `sanitize_untrusted_text`.