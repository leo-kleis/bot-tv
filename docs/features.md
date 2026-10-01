# Herramientas y Funcionalidades de bot-tv

Documentación técnica consolidada de las capacidades, herramientas, componentes e interfaces de la aplicación `bot-tv`.

---

## 1. Visión General e Interfaz Predeterminada

`bot-tv` es un bot interactivo de Twitch con integración de Inteligencia Artificial (Google Gemini), arquitectura dirigida por eventos (*event-driven*), persistencia en PostgreSQL mediante arquitectura híbrida (Prisma + `asyncpg`) y una interfaz de usuario dual: consola CLI y panel web en tiempo real.

### La Aplicación Web como Interfaz Predeterminada y Principal

Aunque la aplicación puede ejecutarse en modo terminal mediante el comando `bot-tv`, **la Aplicación Web (`bot-web`) es la interfaz predeterminada y principal de todo el sistema**. 

Las razones de este diseño radican en:

1. **Desacoplamiento y Control Multidispositivo (PWA)**:
   - Permite operar y moderar el stream desde ordenadores secundarios, tablets o teléfonos móviles mediante la red local (`http://<ip-host>:8080` o `https://<ip-host>:8080`), sin consumir recursos de pantalla en el monitor de transmisión.
   - Implementa soporte PWA completo con [`manifest.json`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/manifest.json) y [`sw.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/sw.js), permitiendo su instalación como aplicación nativa en dispositivos móviles.

2. **Riqueza Interactiva y Multimedia**:
   - Muestra avatares de usuarios, badges dinámicos de suscripción (T1/T2/T3, VIP, Mod, Bot), renderizado de emotes nativos de Twitch, BetterTTV y FrankerFaceZ.
   - Incluye el reproductor de video en vivo de Twitch integrado, búsqueda visual con carátulas de videojuegos para el cambio de categorías y paneles laterales deslizantes (*drawers*) con historial de mensajes.

3. **Herramientas de Filtrado y Gestión Masiva**:
   - Proporciona una tabla interactiva para consultar y filtrar miles de usuarios por roles, estado de seguimiento, rangos de fechas y presencia en chat, acciones imposibles de operar con agilidad mediante una línea de comandos.

4. **Bucle Asíncrono Unificado y Cero Latencia**:
   - En [`web_main.py`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web_main.py), el servidor web ASGI (Starlette + Uvicorn), el cliente del bot de Twitch (TwitchIO), el bus de eventos y el agente conversacional se ejecutan en el mismo loop de eventos (`asyncio.wait([bot_task, server_task], return_when=FIRST_COMPLETED)`), logrando una propagación instantánea por WebSocket sin demoras de red entre procesos.

---

## 2. Aplicación Web y Dashboard (`src/bot_tv/web/`)

### 2.1 Tecnologías y Arquitectura Frontend
- **Zero-Build ESM**: Desarrollo sin compiladores ni empaquetadores (sin Vite ni Webpack). Usa módulos ESM nativos del navegador con `<script type="importmap">`, cargando Preact, Preact Hooks y HTM desde el directorio de recursos locales.
- **WebSocket Reactivo (`useWebSocket.js`)**:
  - Reconexión adaptativa con retroceso exponencial.
  - Reconexión proactiva en dispositivos móviles ante eventos del sistema: cambio de visibilidad (`visibilitychange`), recuperación de red (`online`), retorno desde caché del navegador (`pageshow`) y foco de ventana (`focus`).
  - Sincronización automática de eventos históricos acumulados al conectarse (`history_end`).
- **Sistema de Estilos y Responsive Design**:
  - CSS modular organizado en 18 hojas de estilo.
  - Breakpoints mutuamente excluyentes (móvil vertical `max-width: 600px`, modo apaisado `max-height: 480px`, tablet/escritorio `min-width: 601px` y `min-height: 481px`).
  - Sistema estricto de capas visuales y `z-index` normalizado por variables CSS.

### 2.2 Pestañas y Componentes del Dashboard

| Pestaña / Vista | Componente Principal | Funcionalidades Principales |
|---|---|---|
| **Chat** | [`ChatTab.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/components/chat/ChatTab.js) | - Visualización de mensajes en tiempo real con avatares y colores contrastados.<br>- Renderizado de emotes (Twitch, BTTV y proxy FFZ).<br>- Badges visuales de roles (Broadcaster, Mod, VIP, Sub T1/T2/T3, Bot).<br>- Menú contextual por mensaje: ver ficha de usuario o eliminar mensaje de Twitch.<br>- Eventos formateados: raids, subs, cheers de bits, canjes de puntos, predicciones, baneos y clips.<br>- Selector de cuenta emisora para hablar como Bot o como Streamer.<br>- Botón de limpieza global de sala (`/clear`) con confirmación modal.<br>- Botón de clip instantáneo (atajo F6).<br>- Filtro para ocultar mensajes de cuentas bot.<br>- Botón flotante para descender al último mensaje cuando hay scroll.<br>- Panel lateral deslizable de presencia IRC con listas de usuarios conectados y desconectados. |
| **Stream** | [`StreamTab.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/components/stream/StreamTab.js) | - Reproductor interactivo oficial embebido de Twitch (`Twitch.Player`).<br>- Desactivación automática inteligente en pantallas táctiles y móviles para optimizar batería y datos. |
| **Seguidores / Usuarios** | [`FollowersTab.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/components/followers/FollowersTab.js) | - Tarjetas de métricas: total de seguidores, altas y bajas en la sesión activa.<br>- Barra interactiva con porcentaje en vivo del proceso de sincronización con la API de Twitch.<br>- Botón de sincronización manual con protección contra llamadas concurrentes.<br>- Filtro por texto en nombre de usuario o apodo con debounce.<br>- Filtros por rol (Mod, VIP, Sub, Bot, Visitante).<br>- Filtros por estado de seguimiento (Seguidor activo, Dejó de seguir, Nunca siguió).<br>- Filtros por historial (Con mensajes registrados o Sin mensajes).<br>- Filtro por rangos de fecha ("desde - hasta") de seguimiento o baja.<br>- Tabla con paginación de 50 registros y ordenamiento dinámico por columnas.<br>- Botón de acceso directo para abrir el perfil extendido de cada usuario. |
| **Agente IA** | [`AgentTab.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/components/agent/AgentTab.js) | - Interfaz de chat directa con el asistente Google Gemini.<br>- Indicador en tiempo real de consumo de cuotas del modelo (RPM actual vs límite y estado de bloqueo con cuenta regresiva).<br>- Indicación del modelo exacto que generó cada respuesta (incluyendo avisos de fallback).<br>- Botón para vaciar la memoria conversacional del agente.<br>- Atajos de teclado: Shift+Enter para nueva línea, Enter para enviar. |
| **Ajustes** | [`SettingsTab.js`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/web/static/components/settings/SettingsTab.js) | - **Modelo IA**: Selector de modelo Gemini en caliente y ajuste numérico del límite de turnos de contexto (0 = ilimitado).<br>- **Chat**: Control deslizante de tamaño de fuente (12px a 22px) con previsualización en vivo persistido en `localStorage` e interruptor para ocultar bots.<br>- **Hardware Host (Audio)**: Control del servicio anti-suspensión de auriculares inalámbricos en el PC anfitrión, ajuste de volumen (0.5% - 15%), indicador luminoso de ejecución en segundo plano y botón de prueba sonora.<br>- **Zona de Peligro**: Botón para apagar de forma ordenada todo el sistema (bot, servidor web y base de datos) con modal de confirmación. |

### 2.3 Controles Globales, Modales y Drawers

- **Widget de Encabezado (`StreamWidget.js`)**: Muestra estado LIVE/OFFLINE, uptime en tiempo real (`HH:MM:SS`), espectador actual, título y categoría. Al hacer clic sobre el título/categoría, abre el modal de edición de stream.
- **Modal de Edición de Stream (`StreamEditModal.js`)**: Permite cambiar el título del stream (contador de 140 caracteres) y buscar categorías o videojuegos en vivo mediante la API de Twitch con visualización de carátulas (`box_art_url`).
- **Popover de Conexiones (`ConnectionIndicator.js`)**: Semáforo visual en el header que despliega un popover detallando el estado individual de la conexión con el servidor web y la sesión IRC con Twitch.
- **Drawer de Perfil de Usuario (`UserProfileDrawer.js`)**: Panel lateral deslizable con tres pestañas:
  1. *Detalle y Apodo*: Enlace a Twitch, fecha de seguimiento y formulario para asignar o borrar apodo local.
  2. *Roles y Moderación*: Asignación de roles en base de datos, sincronización en vivo con Twitch Helix, estado de baneo en Twitch (permanente o timeout con expiración y motivo) y botones de acción: purga de mensajes (timeout de 1 segundo), baneo permanente y desbaneo.
  3. *Historial de Mensajes*: Historial completo de mensajes del usuario con buscador textual, filtros de fecha desde/hasta y scroll infinito paginado.
- **Sistema de Alertas Toast (`ToastOverlay.js`)**: Notificaciones emergentes con agrupación inteligente de altas y bajas de seguidores y filtrado selectivo según la pestaña en pantalla.

---

## 3. Catálogo de la API REST (`src/bot_tv/web/api/`)

Todos los endpoints responden con formato estándar JSON: `{ "ok": true, "data": ... }` o `{ "ok": false, "error": ... }`.

### 3.1 Agente de IA (`agent.py`)
- `POST /api/talk`: Envía un mensaje al agente conversacional y devuelve la respuesta generada.
- `POST /api/switch_model`: Cambia en caliente el modelo activo de Gemini.
- `POST /api/agent/clear`: Limpia el historial de turnos de memoria del agente.
- `POST /api/agent/context_limit`: Modifica y persiste el límite máximo de turnos conversacionales recordados.
- `GET /api/rpm`: Consulta el consumo de peticiones por minuto (RPM) y por día (RPD), próximo slot disponible y bloqueos del modelo activo o de todos (`?all=true`).
- `GET /api/models`: Lista los modelos Gemini disponibles, sus límites y su estado de habilitación.

### 3.2 Moderación en Twitch (`moderation.py`)
- `POST /api/moderation/ban`: Aplica baneo permanente a un usuario en Twitch mediante Helix API con motivo opcional.
- `POST /api/moderation/unban`: Remueve la sanción o baneo a un usuario en Twitch.
- `POST /api/moderation/purge`: Aplica una purga de mensajes en la sala mediante un timeout de 1 segundo en Twitch.
- `POST /api/moderation/delete_message`: Elimina un mensaje puntual por su ID en Twitch o ejecuta una limpieza global de chat (`/clear`) si no se indica ID.

### 3.3 Gestión de Stream e Información (`stream.py`)
- `GET /api/categories/search`: Busca videojuegos y categorías en Twitch (`?query=...`) devolviendo nombres, IDs y carátulas.
- `POST /api/stream/update_info`: Actualiza el título de la transmisión y/o el identificador de categoría en Twitch Helix.

### 3.4 Chat y Emotes (`chat.py`)
- `GET /api/chat_accounts`: Devuelve las cuentas autorizadas para emitir mensajes en el chat (Streamer o Bot).
- `POST /api/send_chat_message`: Envía un mensaje al chat en vivo de Twitch utilizando las credenciales de la cuenta remitente elegida.
- `GET /api/emotes/ffz/{channel_id}`: Proxy inverso asíncrono hacia FrankerFaceZ con caché local para prevenir errores 404 en el cliente.

### 3.5 Usuarios, Roles y Seguidores (`users.py`)
- `POST /api/sync_followers`: Inicia la sincronización en segundo plano de seguidores desde la API de Twitch.
- `POST /api/set_nickname`: Establece o borra el apodo local de un usuario.
- `POST /api/update_user_roles`: Actualiza manualmente los roles de un usuario en la base de datos (bot, mod, vip).
- `POST /api/sync_user_roles`: Consulta las APIs de Twitch en vivo y sincroniza los roles del usuario con la base de datos.
- `GET /api/users/search`: Autocompletado predictivo de usuarios en base de datos.
- `GET /api/users`: Listado paginado de usuarios con filtros avanzados de rol, seguimiento, historial de mensajes y fechas.
- `GET /api/avatar/{user_id}`: Redirección HTTP 302 hacia la URL de imagen de perfil de Twitch almacenada en caché.
- `GET /api/users/{username}/detail`: Ficha completa del usuario con roles, apodo, estado de baneo en Twitch y fechas de seguimiento.
- `GET /api/users/{username}/messages`: Historial paginado de mensajes de chat emitidos por el usuario con filtros de texto y fechas.

### 3.6 Hardware y Utilidades Host (`audio.py`)
- `GET /api/audio_keepalive`: Estado del servicio anti-suspensión de auriculares en el PC anfitrión (estado de ejecución, volumen y frecuencia).
- `POST /api/audio_keepalive`: Activa, desactiva o ajusta los parámetros del generador de tono senoidal persistente.
- `POST /api/audio_keepalive/test`: Emite un tono sonoro audible de prueba en los altavoces del PC anfitrión mediante un hilo desacoplado.

### 3.7 Sistema y Clips (`system.py`)
- `POST /api/create_clip`: Genera un clip instantáneo del directo en emisión a través de la API Helix de Twitch.
- `POST /api/exit`: Solicita el apagado ordenado de toda la aplicación.

---

## 4. Agente de Inteligencia Artificial (`src/bot_tv/agent/`)

El asistente conversacional utiliza el SDK `google-antigravity` conectado a Google Gemini. Está diseñado como una herramienta administrativa exclusiva del operador.

### 4.1 Modelos y Configuración (`models.py`)
| Modelo | Display Name | Límites Operativos | Estado | Rol |
|---|---|---|---|---|
| `gemini-3.1-flash-lite` | Gemini 3.1 Flash Lite | 30 RPM \| 1.500 RPD \| 1M TPM | Habilitado | **Predeterminado** |
| `gemini-2.5-flash` | Gemini 2.5 Flash | 15 RPM \| 1.500 RPD \| 1M TPM | Habilitado | Secundario / Fallback |
| `gemini-2.0-flash` | Gemini 2.0 Flash | 15 RPM \| 1.500 RPD \| 1M TPM | Habilitado | Secundario / Fallback |
| `gemini-3-flash-preview`| Gemini 3 Flash Preview | 15 RPM \| 1.500 RPD \| 1M TPM | Habilitado | Secundario / Fallback |
| `gemini-flash-latest` | Gemini Flash Latest | 15 RPM \| 1.500 RPD \| 1M TPM | Habilitado | Secundario / Fallback |
| `gemini-2.5-pro` | Gemini 2.5 Pro | 2 RPM \| 50 RPD \| 32K TPM | Deshabilitado | Restringido por cuota gratuita |

### 4.2 Control de Cuotas y Sistema de Fallback (`rate_limiter.py` y `client.py`)
- **Ventanas Deslizantes Globales**: Monitorea el consumo por modelo con colas temporales dobles (últimos 60 segundos y últimas 24 horas).
- **Persistencia de Consumo**: Cada llamada y cada incidente de saturación se guarda en la tabla `api_consumption_log`, permitiendo reconstruir las ventanas de uso tras reiniciar el bot.
- **Fallback Preventivo**: Si el modelo activo alcanza su límite de RPM o RPD antes de disparar la llamada, desvía automáticamente la consulta al modelo habilitado con mayor margen disponible.
- **Fallback Reactivo**: Si la API de Google responde con error de cuota (HTTP 429, 503 o sobrecarga de recursos), aplica un bloqueo temporal al modelo, registra la penalización y reintenta inmediatamente la petición con el mejor modelo de reemplazo anteponiendo `[Fallback: <nombre_modelo>]`.
- **Ventana de Contexto Adaptativa**: Permite limitar la cantidad de turnos anteriores inyectados en el prompt (`agent_context_limit`), controlando el consumo de tokens en sesiones extensas.

### 4.3 Herramientas de Consulta y Control (Function Calling)
El agente dispone de 11 herramientas registradas en [`src/bot_tv/agent/tools/`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/agent/tools/) para consultar la base de datos o interactuar con Twitch:

1. **Gestión de Seguidores (`channel_users.py`)**:
   - `get_channel_user_stats`: Devuelve total histórico, seguidores activos y unfollows en la base de datos.
   - `search_channel_users`: Búsqueda de seguidores por coincidencia parcial de texto en nombre o apodo.
   - `get_channel_user_info`: Obtiene la ficha de seguimiento detallada de un usuario por su nombre.
   - `get_recent_channel_users`: Devuelve los últimos seguidores registrados en el canal.
   - `get_recent_channel_unfollowers`: Lista los usuarios que dejaron de seguir el canal recientemente con sus fechas.
2. **Historial y Métricas de Chat (`chat.py`)**:
   - `get_chat_messages`: Busca mensajes en el registro histórico con filtros combinables (usuario, término de búsqueda, rol, antigüedad relativa en horas o rango absoluto de fechas ISO).
   - `get_chat_stats`: Resumen del volumen total de mensajes, usuarios únicos participantes y el Top 5 de chatters más activos.
3. **Gestión de Transmisión y VODs (`stream.py`)**:
   - `change_stream_title`: Modifica el título de la transmisión en Twitch Helix reportando el cambio antes y después.
   - `change_stream_category`: Busca el juego en Twitch Helix, obtiene su identificador oficial y actualiza la categoría.
   - `get_stream_info`: Consulta el estado en vivo (título, categoría y viewers) o los últimos metadatos configurados si está offline.
   - `get_history_vod_streams`: Consulta emisiones pasadas (VODs) en Twitch y calcula en la base de datos local el volumen exacto de mensajes de chat registrados durante el tiempo que estuvo al aire cada directo.
4. **Catálogo de Usuarios (`users.py`)**:
   - `get_user_info`: Consulta la ficha general de un usuario en la base de datos (nombres, apodo, roles y seguimiento).
   - `list_users`: Lista usuarios registrados con paginación y filtros por rol o búsqueda textual.

---

## 5. Acciones, Componentes y EventBus

### 5.1 Bus de Eventos (`event_bus.py`)
Implementa un patrón Publicador/Suscriptor asíncrono desacoplado:
- Despacho tolerante a fallos: La excepción en un suscriptor no detiene el envío al resto.
- Buffer circular histórico (`deque(maxlen=500)`): Permite a clientes que se reconectan al WebSocket recuperar los últimos eventos sucedidos.
- Tipos de eventos inmutables `@dataclass(frozen=True, slots=True)` en [`events.py`](file:///c:/Users/kleis/Repo/bot-tv/src/bot_tv/events.py).

### 5.2 Componentes Modulares de Twitch (`src/bot_tv/components/`)
- **`ChatComponent`**:
  - Emite `ChatMessageEvent` en menos de 1 milisegundo resolviendo roles y colores desde la caché en memoria.
  - Tarea en segundo plano `_enrich_and_persist`: guarda mensajes en PostgreSQL, actualiza roles de canal y descarga avatares diferidos.
  - Comandos de chat integrados: `?hola` (saludo) y `?eleccion <opción 1> <opción 2> ...` (elección aleatoria).
- **`ClipComponent`**:
  - Escucha el atajo de teclado global **`F6`** mediante la librería `keyboard`.
  - Verifica que el canal esté en vivo y genera el clip a través de Helix API (`create_clip`) con el token del broadcaster.
  - Emite `ClipCreatedEvent` con el enlace resultante.
- **`FollowersComponent`**:
  - Sincronización automática de seguidores al conectar el bot y sincronización manual bajo demanda.
  - Consulta paginada a la API de Twitch, cálculo diferencial en memoria contra la base de datos y emisión de eventos de progreso en tiempo real (`FollowerProgressEvent` y `FollowerSyncEvent`).
  - Actualización atómica en base de datos registrando solo altas y bajas.
- **`StreamComponent`**:
  - Escucha eventos EventSub de stream online, stream offline y actualización de canal.
  - Polling de viewers cada 60 segundos (`_viewer_poll_loop`), calculando la diferencia (`diff`) de espectadores para emitir `ViewerUpdateEvent`.
- **`TwitchEventsComponent`**:
  - Puente entre TwitchIO EventSub y el `EventBus` para: Seguidores, Raids, Suscripciones (nuevas, regaladas, mensajes de resub con rachas), Donaciones de Bits (cheers), Canjes de puntos de canal, Ciclo de vida de predicciones (inicio, progreso de apuestas, bloqueo y finalización) y Moderación (baneos, timeouts, desbaneos, `/clear`, purgas y borrado de mensajes).

### 5.3 Consumidor de Terminal (`src/bot_tv/consumers/terminal.py`)
Suscrito a 17 eventos del `EventBus` para renderizar en la consola de texto mediante la librería `Rich`:
- Mensajes de chat con colores RGB originales del usuario, timestamps y apodos.
- Entradas (`JOIN`) y salidas (`PART`) de la sala IRC.
- Alertas estilizadas para todos los eventos de Twitch EventSub y cambios en la transmisión.

---

## 6. Persistencia y Base de Datos (`src/bot_tv/database/`)

### 6.1 Arquitectura Híbrida
- **Prisma v7**: Define el modelo de datos en [`prisma/schema.prisma`](file:///c:/Users/kleis/Repo/bot-tv/prisma/schema.prisma) y gestiona las migraciones estructuradas mediante TypeScript / Node.js.
- **`asyncpg`**: El backend en Python se conecta directamente a PostgreSQL con consultas SQL nativas (`raw queries`) optimizadas, prescindiendo de ORMs en tiempo de ejecución.
- **Pool de Conexiones (`connection.py`)**: `create_pg_pool` utiliza `DIRECT_URL` para evitar interferencias con poolers transaccionales como PgBouncer, deshabilitando el caché de sentencias preparadas (`statement_cache_size=0`) para máxima estabilidad.

### 6.2 Entidades Persistidas
1. **`users`**: ID de Twitch, nombre de usuario, nombre visible, apodo asignado, indicador de bot y URL del avatar.
2. **`channel_users`**: Relación de canal y usuario: fecha de follow, fecha de unfollow, roles (`is_moderator`, `is_vip`, `is_subscriber`), nivel de suscripción (`sub_tier`) y usuario donador (`gifter_id`).
3. **`chat_history`**: Registro histórico de mensajes con UUID, canal, ID de usuario, mensaje y timestamp ISO. Índice compuesto en `(channel_id, user_id)`.
4. **`tokens`**: Credenciales OAuth (Access Token y Refresh Token) cifradas simétricamente con `Fernet`.
5. **`app_settings`**: Almacén clave-valor para configuraciones globales (modelo activo, límite de contexto conversacional, etc.).
6. **`api_consumption_log`**: Registro de peticiones y bloqueos de la API de IA con marca de tiempo Unix y tipo de consumo.

### 6.3 Caché en Memoria (`UserMemoryCache`)
Mantiene diccionarios en RAM con todos los usuarios y sus roles por canal:
- Precarga masiva en el arranque (`preload_cache`).
- Comprueba si existen modificaciones antes de emitir queries de actualización (`needs_user_update` y `needs_roles_update`), reduciendo drásticamente las escrituras en disco.
- Resuelve búsquedas, filtrado y paginación en memoria para el panel de usuarios.

### 6.4 Buffer de Mensajes en Lote (`ChatRepository`)
Los mensajes entrantes del chat se encolan en memoria y un worker en segundo plano (`_batch_loop`) realiza el volcado masivo en PostgreSQL cada 2 segundos o al alcanzar 20 mensajes acumulados, evitando bloqueos de I/O en chats de alto tráfico.

---

## 7. Consola Interactiva CLI y Entrypoints

### 7.1 Puntos de Entrada (`pyproject.toml`)
- **`bot-web` (`src/bot_tv/web_main.py`)**: Entrypoint predeterminado. Inicia el bot de Twitch y el servidor web con dashboard en tiempo real.
- **`bot-tv` (`src/bot_tv/main.py`)**: Inicia el bot de Twitch junto con la consola REPL interactiva en la terminal y el consumidor Rich.
- **`bot-setup` (`src/bot_tv/setup.py`)**: Asistente interactivo por consola para vincular las cuentas de Twitch (Bot y Canal) mediante OAuth Device Code Flow (DCF), solicitando 22 scopes para el bot y 28 scopes para el canal, y guardando los tokens cifrados con Fernet en PostgreSQL.

### 7.2 Comandos de la Consola CLI (`src/bot_tv/console/`)
La consola REPL interactiva (`AdminConsole`) incorpora autocompletado contextual asíncrono con la base de datos (`BotCompleter`):
- `sync_followers`: Sincroniza la lista de seguidores de Twitch con la base de datos local.
- `is_bot <usuario>`: Alterna la condición de bot de una cuenta.
- `apodo <usuario> [apodo]`: Asigna o remueve el apodo personalizado del usuario.
- `talk <mensaje>`: Envía una consulta directa a Google Gemini desde la terminal con indicador de progreso.
- `rpm [all]`: Muestra el estado del limitador de tasa (RPM, RPD y estado de bloqueo) del modelo activo o de todos.
- `model [nombre]`: Consulta el modelo activo o cambia a otro modelo de Gemini en tiempo de ejecución.
- `models`: Lista los modelos configurados en AI Studio y sus cuotas.
- `help`: Imprime la ayuda de los comandos.
- `exit`: Cierre ordenado del bot, base de datos y conexiones activas.

---

## 8. Utilidades Adicionales (`extra/`)

- [`extra/migrate_to_pg.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/migrate_to_pg.py): Script de migración atómica para transferir datos antiguos desde SQLite local (`app.db` y `tokens.db`) hacia PostgreSQL.
- [`extra/check_scopes.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/check_scopes.py): Herramienta de diagnóstico que descifra los tokens de la base de datos y valida su vigencia y scopes contra la API de Twitch.
- [`extra/check_twitch_id.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/check_twitch_id.py): Consulta un ID numérico de usuario en la API Helix y muestra sus datos públicos.
- [`extra/get_twitch_ids.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/get_twitch_ids.py): Asistente para resolver nombres de usuario a IDs de Twitch requeridos para el archivo `.env`.
- [`extra/keepalive_audio.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/keepalive_audio.py): Servicio autónomo de Windows que genera un tono senoidal inaudible en bucle a 60 Hz al 3% de volumen para evitar que altavoces o auriculares Bluetooth entren en reposo, consumiendo 0% de CPU.
- [`extra/run_migrations.py`](file:///c:/Users/kleis/Repo/bot-tv/extra/run_migrations.py): Comprueba la conectividad con PostgreSQL y lista las tablas del esquema público.
