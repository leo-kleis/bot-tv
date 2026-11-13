# Documentación de la Base de Datos

Este documento describe la arquitectura de la base de datos de **bot-tv**, su diseño relacional en **Prisma Postgres (Prisma Console)** y el flujo de trabajo para realizar modificaciones en el esquema.

---

## 1. Arquitectura Híbrida (Prisma Console + `asyncpg`)

El proyecto utiliza una arquitectura de base de datos dividida sobre **Prisma Postgres (Prisma Console)**:

1. **Gestión del Esquema y Migraciones (Prisma v7):**
   Toda la estructura física de la base de datos (tablas, claves primarias, claves foráneas e índices) se define y gestiona en el archivo [schema.prisma](../prisma/schema.prisma) usando TypeScript/Node.js.

2. **Ejecución y Consultas en Producción (Python + `asyncpg`):**
   El backend en Python se conecta directamente a PostgreSQL mediante la librería `asyncpg` y ejecuta sentencias SQL parametrizadas de alto rendimiento a través de los repositorios en `src/bot_tv/database/repositories/`, los cuales heredan de `BaseRepository` con soporte de reintentos automáticos (`_with_retry`) ante desconexiones transitorias.

3. **Caché en Memoria y Precarga Asíncrona (`UserMemoryCache`):**
   Para minimizar la latencia en el chat en vivo y en la búsqueda de usuarios, `UserMemoryCache` precarga en memoria en segundo plano durante el arranque los registros de usuarios y seguidores, permitiendo fallback transparente directo a PostgreSQL mientras la precarga completa su ejecución.

---

## 2. Modelos de la Base de Datos

### Tabla: `users`

Almacena la información global de los usuarios que interactúan con el bot.

- `user_id` (TEXT, PK): ID único de usuario de Twitch.
- `username` (TEXT, indexado): Nombre de usuario en minúsculas.
- `display_name` (TEXT): Nombre para mostrar en el chat.
- `nickname` (TEXT): Apodo personalizado asignado en el bot.
- `is_bot` (BOOLEAN): Indica si la cuenta es un bot.
- `profile_image_url` (TEXT): URL de la imagen de perfil de Twitch.
- **Índices:** `idx_users_username` (`username`), `idx_users_username_lower` (`LOWER(username)`).

### Tabla: `channel_users`

Representa la relación de cada usuario con cada canal en el que el bot está activo, incluyendo su seguimiento y roles específicos del canal.

- `channel_id` (TEXT, PK): ID del canal (broadcaster) al que pertenece el usuario.
- `user_id` (TEXT, PK, FK): ID del usuario que apunta a `users.user_id`.
- `followed_at` (TIMESTAMPTZ): Fecha y hora en la que comenzó a seguir.
- `unfollowed_at` (TIMESTAMPTZ): Fecha y hora en la que dejó de seguir.
- `is_moderator` (BOOLEAN): Indica si es moderador en este canal específico.
- `is_vip` (BOOLEAN): Indica si tiene rango VIP en este canal específico.
- `is_subscriber` (BOOLEAN): Indica si está suscrito a este canal específico.
- `sub_tier` (TEXT): Nivel de suscripción (`"1000"` | `"2000"` | `"3000"`).
- `gifter_id` (TEXT): ID de usuario de quien regaló la suscripción.
- **Índices:** `idx_channel_users_followed` (`channel_id, followed_at DESC`), `idx_channel_users_unfollowed` (`channel_id, unfollowed_at DESC`), `idx_channel_users_gifter_id` (`gifter_id`).

Consultas analíticas asociadas:

- `AnalyticsRepository.get_followers_balance(channel_id, start_at, end_at)`: calcula el recuento de nuevos seguidores (`followed_at`), bajas (`unfollowed_at`) y el balance neto dentro del intervalo temporal de una sesión de transmisión.
- `AnalyticsRepository.get_session_follower_events(channel_id, stream_id)`: consulta los eventos individuales de alta (`follow`) y baja (`unfollow`) ocurridos durante la sesión mediante una unión `UNION ALL` y `LEFT JOIN users` acotada al intervalo `[started_at, COALESCE(ended_at, NOW())]` (coincidente con los límites temporales de `get_followers_balance`), devolviendo la lista cronológica de eventos (`events`), el recuento de altas (`new_count`) y de bajas (`lost_count`).

### Tabla: `chat_history`

Almacena el historial de mensajes de los canales.

- `id` (UUID, PK): Identificador único del mensaje.
- `channel_id` (TEXT): ID del canal donde se escribió el mensaje.
- `user_id` (TEXT, FK): ID del usuario que envió el mensaje (`users.user_id`).
- `message` (TEXT): Contenido del mensaje de chat.
- `timestamp` (TIMESTAMPTZ): Marca de tiempo del mensaje.
- `stream_id` (TEXT, nullable): Identificador de la sesión de stream activa cuando se envió el mensaje.
- **Índices:** `idx_chat_history_channel_user` (`channel_id, user_id`), `idx_chat_history_channel_ts` (`channel_id, timestamp DESC`), `idx_chat_history_stream_ts` (`stream_id, timestamp`).

A través de `AnalyticsRepository.get_session_messages(channel_id, stream_id, since=None, until=None, user_id=None, limit=100, offset=0)`, se consultan mensajes vinculados a una sesión (`c.channel_id = $1 AND c.stream_id = $2`) uniendo `chat_history` con `users`, aplicando filtros de rango semiabierto `[since, until)` (`timestamp >= since` y `timestamp < until`) y usuario (`user_id`), devolviendo el recuento exacto (`total`), los registros paginados y el indicador booleano `has_more`.

### Tabla: `stream_sessions`

Registra cada sesión de transmisión en vivo del canal para el módulo de Analíticas.

- `stream_id` (TEXT, PK): Identificador único de la sesión de stream en Twitch.
- `channel_id` (TEXT): ID del canal.
- `title` (TEXT, nullable): Título del directo.
- `category_name` (TEXT, nullable): Categoría o juego transmitido.
- `is_live` (BOOLEAN): Indica si la sesión continúa en vivo.
- `started_at` (TIMESTAMPTZ): Fecha y hora de inicio del stream.
- `ended_at` (TIMESTAMPTZ, nullable): Fecha y hora de finalización del stream (`NULL` si continúa en vivo).
- `last_seen_at` (TIMESTAMPTZ): Última marca de tiempo de actividad registrada en la sesión.
- `peak_viewers` (INTEGER): Pico máximo de espectadores simultáneos alcanzado en la sesión.
- `close_reason` (TEXT, nullable): Motivo de cierre de la sesión (`stream_offline`, `stale_cleanup`, etc.).
- **Índice:** `idx_stream_sessions_channel_started` (`channel_id, started_at DESC`).

### Tabla: `viewer_snapshots`

Muestras periódicas de espectadores simultáneos asociadas a una sesión de transmisión.

- `id` (BIGINT, PK, Autoincremental).
- `stream_id` (TEXT, FK): Referencia a `stream_sessions.stream_id` (`ON DELETE CASCADE`).
- `channel_id` (TEXT): ID del canal.
- `viewer_count` (INTEGER): Cantidad de espectadores en el instante del muestreo.
- `recorded_at` (TIMESTAMPTZ): Marca de tiempo de la muestra.
- **Índice:** `idx_viewer_snapshots_stream_ts` (`stream_id, recorded_at DESC`).

A través de `AnalyticsRepository.get_viewer_stats(stream_id)`, se calculan de forma agregada el promedio de espectadores (`avg_viewers`), el pico máximo (`peak_viewers`) y el número de muestras (`sample_count`) de una sesión.

### Tabla: `stream_events`

Registro histórico de eventos ocurridos en el canal (raids, suscripciones, bits, canjes de puntos, predicciones, moderación).

- `id` (BIGINT, PK, Autoincremental).
- `stream_id` (TEXT, FK, nullable): Referencia a `stream_sessions.stream_id` (`ON DELETE SET NULL`).
- `channel_id` (TEXT): ID del canal.
- `event_type` (TEXT): Tipo de evento (`follow`, `raid`, `sub`, `sub_gift`, `sub_message`, `cheer`, `points_redeem`, `ban`, `unban`, `clip`, etc.).
- `event_data` (JSONB): Payload estructurado del evento en formato JSON.
- `timestamp` (TIMESTAMPTZ): Fecha y hora del evento.
- **Índices:** `idx_stream_events_stream_ts` (`stream_id, timestamp DESC`), `idx_stream_events_stream_type` (`stream_id, event_type`), `idx_stream_events_event_data_gin` (GIN sobre `event_data`).

A través de `AnalyticsRepository.get_stream_event_summary(stream_id)`, se agrupan los eventos por `event_type` y `reward_title` (extrayendo el nombre de la recompensa para `channel_points` mediante `event_data->>'reward_title'`), calculando el conteo total de eventos (`event_count`) y la métrica acumulada (`total_metric_value` para bits, espectadores de raids o costo de recompensas).

### Tabla: `tokens`

Persistencia de tokens OAuth encriptados simétricamente con arquitectura de claves múltiples (`MultiFernet`).

- `user_id` (TEXT, PK): ID de Twitch.
- `username` (TEXT): Nombre de usuario.
- `token` (TEXT): Access token encriptado.
- `refresh` (TEXT): Refresh token encriptado.

#### Cifrado y Rotación de Claves (`MultiFernet`)

El subsistema de seguridad en `src/bot_tv/utils/security.py` opera con un paquete `MultiFernet` que garantiza retrocompatibilidad y migración sin fricciones:

1. **Clave Primaria (`ENCRYPTION_KEY`)**: Si está definida en `.env`, se utiliza para cifrar todos los tokens nuevos o actualizados.
2. **Derivación HKDF (`TWITCH_CLIENT_SECRET`)**: Si no se provee `ENCRYPTION_KEY`, se deriva una clave simétrica de 32 bytes mediante HKDF (SHA-256) a partir del secret de Twitch.
3. **Desencriptación de Respaldo**: Al descifrar, `MultiFernet` prueba la clave primaria y las claves derivadas legacy (HKDF, PBKDF2HMAC con 600.000 iteraciones y SHA-256).
4. **Rotación Automática**: `decrypt_token_with_rotation` detecta si el token fue descifrado con una clave anterior y genera el nuevo payload cifrado para actualizarlo en PostgreSQL de forma transparente.

### Tabla: `app_settings`

Configuraciones clave-valor globales de la aplicación. Nota: la clave `agent_context_limit` fue retirada de base de datos; el límite de contexto del agente se configura directamente en código mediante la constante `AGENT_CONTEXT_LIMIT` en `src/bot_tv/agent/client.py`.

- `key` (TEXT, PK): Nombre de la configuración.
- `value` (TEXT): Valor de la configuración.

### Tabla: `api_consumption_log`

Historial de consumo y bloqueos de cuota del modelo LLM (Google Gemini).

- `id` (BIGINT, PK, Autoincremental).
- `model` (TEXT): Nombre del modelo consumido.
- `timestamp` (DOUBLE PRECISION): Fecha y hora en formato Unix epoch.
- `type` (TEXT): Tipo de registro (`request` o `block_<segundos>`).
- **Índice:** `idx_api_consumption_ts` (`timestamp`).

---

## 3. Flujo para modificar o agregar tablas/columnas

### Paso 1: Modificar el esquema

Abre [schema.prisma](../prisma/schema.prisma) y realiza los cambios en los modelos correspondientes.

### Paso 2: Generar y aplicar la migración

#### A) Aplicar migraciones ya creadas en el repositorio (Recomendado tras cambios en `prisma/migrations/`)

```bash
pnpm run prisma:deploy
```

#### B) Crear una nueva migración desde tu terminal local

```bash
pnpm run prisma:migrate -- --name <nombre_descriptivo_de_migracion>
```

#### C) Sincronizar directamente en desarrollo rápido

```bash
pnpm run prisma:push
```

### Paso 3: Sincronizar en la aplicación de Python

Actualiza las sentencias SQL en los archivos de repositorio dentro de `src/bot_tv/database/repositories/` y refleja cualquier cambio de modelo en este documento (`docs/database.md`).
