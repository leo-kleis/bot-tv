# Herramientas y Funcionalidades de bot-tv (`v1.0.0-beta.1`)

Documentación técnica consolidada de las capacidades, herramientas, componentes e interfaces de la aplicación `bot-tv`.

---

## 1. Visión General: Arquitectura 100% Web & PWA

`bot-tv` es una aplicación web interactiva (PWA) y bot de Twitch con integración de Inteligencia Artificial (Google Gemini), arquitectura dirigida por eventos (*event-driven*), analíticas de stream en tiempo real y persistencia en PostgreSQL mediante arquitectura híbrida (Prisma + `asyncpg`).

A partir de la versión **`1.0.0-beta.1`**, el proyecto unifica toda su operación en el **Dashboard Web / PWA** (`main.py`), prescindiendo del modo terminal heredado (CLI/REPL):

1. **Desacoplamiento y Control Multidispositivo (PWA)**:
   - Permite operar y moderar el stream desde ordenadores secundarios, tablets o teléfonos móviles mediante la red local (`https://<ip-host>:8080`) o desde la nube (`https://<tu-dominio>`), sin consumir recursos visuales en el monitor de transmisión ni depender de hooks globales del sistema operativo.
   - Implementa soporte PWA completo con `manifest.json` y `sw.js`, permitiendo su instalación como aplicación nativa en móviles y escritorio.

2. **Riqueza Interactiva, Multimedia y Analítica**:
   - Muestra avatares de usuarios, badges dinámicos de suscripción (T1/T2/T3, VIP, Mod, Bot), renderizado de emotes nativos de Twitch, BetterTTV y FrankerFaceZ.
   - Incluye reproductor de video en vivo de Twitch integrado, búsqueda visual con carátulas de videojuegos para cambio de categorías, paneles laterales deslizantes (*drawers*) con historial de mensajes y un módulo completo de **Analíticas de Stream** con gráficos interactivos (Chart.js).

3. **Bucle Asíncrono Unificado y Cero Latencia**:
   - En `src/bot_tv/main.py`, el servidor web ASGI (Starlette + Uvicorn), el cliente del bot de Twitch (TwitchIO), el cliente IRC de presencia, el bus de eventos y el agente conversacional se ejecutan en el mismo loop de eventos (`asyncio.wait([bot_task, server_task], return_when=FIRST_COMPLETED)`), logrando una propagación instantánea por WebSocket.

---

## 2. Aplicación Web y Dashboard (`src/bot_tv/web/`)

### 2.1 Tecnologías y Arquitectura Frontend
- **Empaquetado Ultrarrápido con Vite 8 (Rolldown) + Preact**:
  - Compila los 46 módulos JS y las 19 hojas CSS en `src/bot_tv/web/dist/` en ~230ms (`pnpm run build`).
  - **Code Splitting y Lazy Loading**: Separa automáticamente el runtime (`framework-[hash].js`), la aplicación principal (`index-[hash].js`), el CSS unificado (`style-[hash].css`) y carga bajo demanda el módulo de **Analíticas (`AnalyticsTab-[hash].js` + `chart-[hash].js`)** únicamente cuando el usuario abre la pestaña de Analíticas.
  - En modo `development` (`uv run bot-tv`), el servidor recompila automáticamente con Vite al guardar cambios en `src/bot_tv/web/static/` y notifica recarga en vivo por WebSocket.
- **WebSocket Reactivo (`useWebSocket.js`)**:
  - Reconexión adaptativa con retroceso exponencial y reconexión proactiva en dispositivos móviles (`visibilitychange`, `online`, `pageshow`, `focus`).
  - Sincronización automática del buffer de eventos históricos al conectarse (`history_end`).
- **Sistema de Diseño y Accesibilidad (`.agents/rules/design.md`)**:
  - Breakpoints mutuamente excluyentes:
    - Móvil vertical: `(max-width: 600px) and (min-height: 481px)`
    - Tablet vertical: `(min-width: 601px) and (max-width: 1024px) and (min-height: 481px)`
    - Escritorio: `(min-width: 1025px) and (min-height: 481px)`
    - Modo horizontal (Landscape): `(max-height: 480px)`
  - Cumplimiento WCAG 2.2: aislamiento de modales/drawers con `inert`, trampas de foco (`trapFocus`), navegación por teclado en tablas y listas, y piso tipográfico mínimo de `11px`.

### 2.2 Pestañas y Componentes del Dashboard

| Pestaña / Vista | Componente Principal | Funcionalidades Principales |
|---|---|---|
| **Chat** | `ChatTab.js` | - Visualización de mensajes en tiempo real con avatares y colores contrastados con caché LRU.<br>- Renderizado de emotes (Twitch, BTTV y proxy FFZ).<br>- Badges visuales de roles (Broadcaster, Mod, VIP, Sub T1/T2/T3, Bot).<br>- Menú contextual y soporte de teclado (`Enter`/`Space`) por mensaje y usuario.<br>- Eventos formateados: raids, subs, cheers de bits, canjes de puntos, predicciones, baneos y clips.<br>- Selector de cuenta emisora (Bot o Streamer) e historial de mensajes enviados (`useMessageHistory`).<br>- Botón de limpieza global de sala (`/clear`) con confirmación modal.<br>- Botón de clip instantáneo y atajo de teclado web **`F6`**.<br>- Panel lateral de presencia IRC (fijo en escritorio, drawer deslizable accesible con `inert` y foco en móvil/tablet/landscape). |
| **Stream** | `StreamTab.js` | - Reproductor interactivo oficial embebido de Twitch (`Twitch.Player`).<br>- Desactivación automática inteligente en pantallas táctiles y móviles para optimizar batería y datos. |
| **Seguidores / Usuarios** | `FollowersTab.js` | - Tarjetas de métricas: total de seguidores, altas y bajas en la sesión activa.<br>- Barra de progreso en vivo del proceso de sincronización con Twitch.<br>- Filtros combinables por texto (con debounce), rol, estado de seguimiento, historial de mensajes y rango de fechas.<br>- Tabla con paginación de 50 registros y cabeceras ordenables accesibles por teclado (`aria-sort`). |
| **Analíticas** | `AnalyticsTab.js` | - Selector de sesión de stream o vista global por período (`7d`, `30d`, `90d`, `all`).<br>- Tarjetas de resumen KPI (espectadores pico/promedio, mensajes totales, chatters únicos, nuevos seguidores, eventos).<br>- 5 gráficos interactivos con actualización incremental (`chart.update('none')`): Evolución de Espectadores, Actividad de Chat por intervalo, Top Chatters, Crecimiento de Seguidores y Eventos del Stream. |
| **Agente IA** | `AgentTab.js` | - Interfaz de chat directa con el asistente Google Gemini.<br>- Indicador en tiempo real de consumo de cuotas del modelo (RPM actual vs límite y cuenta regresiva de bloqueo).<br>- Botón para vaciar la memoria conversacional del agente e historial de prompts con flechas arriba/abajo. |
| **Ajustes** | `SettingsTab.js` | - **Modelo IA**: Selector de modelo Gemini en caliente y ajuste numérico del límite de turnos de contexto.<br>- **Chat**: Control deslizante de tamaño de fuente (12px a 22px) e interruptor para ocultar bots.<br>- **Zona de Peligro**: Botón para apagar de forma ordenada todo el sistema con confirmación modal. |

---

## 3. Catálogo de la API REST (`src/bot_tv/web/api/`)

Todos los endpoints responden con formato estándar JSON: `{ "ok": true, "data": ... }` o `{ "ok": false, "error": ... }`.

### 3.1 Agente de IA (`agent.py`)
- `POST /api/talk`: Envía un mensaje al agente conversacional y devuelve la respuesta generada.
- `POST /api/switch_model`: Cambia en caliente el modelo activo de Gemini.
- `POST /api/agent/clear`: Limpia el historial de turnos de memoria del agente.
- `POST /api/agent/context_limit`: Modifica y persiste el límite máximo de turnos conversacionales recordados.
- `GET /api/rpm`: Consulta el consumo de peticiones por minuto (RPM) y por día (RPD).
- `GET /api/models`: Lista los modelos Gemini disponibles, sus límites y su estado de habilitación.

### 3.2 Moderación en Twitch (`moderation.py`)
- `POST /api/moderation/ban`: Aplica baneo permanente a un usuario en Twitch mediante Helix API.
- `POST /api/moderation/unban`: Remueve la sanción o baneo a un usuario en Twitch.
- `POST /api/moderation/purge`: Aplica una purga de mensajes en la sala mediante un timeout de 1 segundo en Twitch.
- `POST /api/moderation/delete_message`: Elimina un mensaje puntual por su `message_id` o ejecuta una limpieza global de chat (`/clear`) únicamente cuando se envía `{ "clear_all": true }` de forma explícita.

### 3.3 Gestión de Stream e Información (`stream.py`)
- `GET /api/categories/search`: Busca videojuegos y categorías en Twitch (`?query=...`).
- `POST /api/stream/update_info`: Actualiza el título de la transmisión y/o el identificador de categoría en Twitch Helix.

### 3.4 Chat y Emotes (`chat.py`)
- `GET /api/chat_accounts`: Devuelve las cuentas autorizadas para emitir mensajes en el chat (Streamer o Bot).
- `POST /api/send_chat_message`: Envía un mensaje al chat en vivo de Twitch utilizando la cuenta elegida.
- `GET /api/emotes/ffz/{channel_id}`: Proxy inverso asíncrono con cliente `httpx.AsyncClient` compartido y caché TTL acotada hacia FrankerFaceZ.

### 3.5 Usuarios, Roles y Seguidores (`users.py`)
- `POST /api/sync_followers`: Inicia la sincronización en segundo plano de seguidores desde la API de Twitch.
- `POST /api/set_nickname`: Establece o borra el apodo local de un usuario.
- `POST /api/update_user_roles`: Actualiza manualmente los roles de un usuario en la base de datos (`bot`, `mod`, `vip`).
- `POST /api/sync_user_roles`: Consulta las APIs de Twitch en vivo y sincroniza los roles del usuario con la base de datos.
- `GET /api/users/search`: Autocompletado predictivo de usuarios en memoria.
- `GET /api/users`: Listado paginado de usuarios con filtros avanzados resueltos en `UserMemoryCache`.
- `GET /api/avatar/{user_id}`: Redirección HTTP 302 hacia la URL de imagen de perfil de Twitch con validación estricta de CDN (`static-cdn.jtvnw.net`).
- `GET /api/users/{username}/detail`: Ficha completa del usuario con roles, apodo, estado de baneo en Twitch y fechas de seguimiento.
- `GET /api/users/{username}/messages`: Historial paginado de mensajes de chat emitidos por el usuario con filtros de texto y fechas.

### 3.6 Analíticas de Stream (`analytics.py`)
- `GET /api/analytics/summary`: Resumen de métricas KPI por sesión (`?stream_id=`) o período (`?period=7d|30d|90d|all`).
- `GET /api/analytics/streams`: Lista las sesiones de stream registradas (`stream_sessions`).
- `GET /api/analytics/viewers_timeline`: Serie temporal de espectadores (`viewer_snapshots`) de una sesión.
- `GET /api/analytics/chat_activity`: Volumen de mensajes y chatters únicos agrupados por intervalos de minutos.
- `GET /api/analytics/top_chatters`: Ranking de usuarios más activos por sesión o período.
- `GET /api/analytics/followers_growth`: Serie diaria de nuevos seguidores y bajas.
- `GET /api/analytics/events_breakdown`: Desglose de eventos del canal (`stream_events`) por tipo y serie temporal.

### 3.7 Sistema y Clips (`system.py`)
- `POST /api/create_clip`: Genera un clip instantáneo del directo en emisión a través de la API Helix de Twitch.
- `POST /api/exit`: Solicita el apagado ordenado de toda la aplicación.

---

## 4. Seguridad y Resiliencia

- **Protección contra Prompt Injection**: Todas las herramientas del agente IA (`src/bot_tv/agent/tools/`) sanitizan textos provenientes de usuarios externos (mensajes de chat, nombres visibles, títulos de premios) mediante `sanitize_untrusted_text` y delimitadores explícitos de datos no confiables.
- **Validación de Redirecciones y URLs**: El endpoint de avatares valida que el destino pertenezca exclusivamente a dominios legítimos de Twitch (`jtvnw.net` / `twitch.tv`), y el frontend sanea las URLs externas con `sanitizeHttpUrl`.
- **Reconexión Automática de Base de Datos**: Todos los repositorios (`ChatRepository`, `AnalyticsRepository`, `TokenRepository`, `SettingsRepository`, `UserRepository`) ejecutan sus consultas a través de `BaseRepository._with_retry`, reconstruyendo el pool `asyncpg` si la base de datos serverless cierra una conexión inactiva.
- **Descifrado Tolerante a Fallos**: `UserMemoryCache.preload_cache` maneja errores `InvalidToken` de forma aislada por registro para que un token corrupto no impida el arranque del servidor.
