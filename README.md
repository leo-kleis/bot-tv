[![Version](https://img.shields.io/badge/version-1.0.0--beta.1-8b5cf6?style=flat-square)](#)
[![Python](https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![TwitchIO](https://img.shields.io/badge/twitchio-v3.3.2-9146FF?style=flat-square&logo=twitch&logoColor=white)](https://twitchio.dev/)
[![Node.js](https://img.shields.io/badge/node.js-v24.12.0-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![Vite](https://img.shields.io/badge/vite-v8.3.6-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![uv](https://img.shields.io/badge/uv-0.13.7-DE5D43?style=flat-square)](https://docs.astral.sh/uv/)
[![pnpm](https://img.shields.io/badge/pnpm-v12.18.0-F69220?style=flat-square&logo=pnpm&logoColor=white)](https://pnpm.io/)
[![Prisma](https://img.shields.io/badge/prisma-v7.9.1-2D3748?style=flat-square&logo=prisma&logoColor=white)](https://www.prisma.io/)
[![License](https://img.shields.io/badge/license-MIT-4ba51c?style=flat-square)](LICENSE)

Aplicación Web interactiva (PWA) y Bot de Twitch con integración de Inteligencia Artificial (Google Gemini), arquitectura _event-driven_, analíticas de transmisión en tiempo real y persistencia híbrida en PostgreSQL (Prisma + `asyncpg`).

- Para una descripción detallada de todas las herramientas, endpoints y funcionalidades del sistema, consulta [docs/features.md](docs/features.md).
- Para el modelo relacional y flujo de migraciones, consulta [docs/database.md](docs/database.md).
- Para la guía de despliegue en servidor / nube con **HTTPS** y **encendido bajo demanda (scale-to-zero)**, consulta [docs/deployment.md](docs/deployment.md).

---

## Características (`v1.0.0-beta.1`)

- **Dashboard Web & PWA Unificado**: Panel de administración visual en tiempo real adaptable a escritorio, tablet y móvil con soporte PWA. Incluye vistas de Chat, Stream, Comunidad, Analíticas enfocadas por sesión y Agente conversacional, con compositor de entrada unificado y control de salida en la cabecera.
- **Frontend Optimizado con Vite**: Bundling moderno con división de código (framework, aplicación y módulo de analíticas bajo demanda), alias de módulos y soporte HMR en desarrollo (`pnpm dev`).
- **Integración Twitch IRC y EventSub**: Conexión nativa con TwitchIO para responder comandos, moderar el chat, crear clips y capturar eventos del canal.
- **Analíticas de Stream en Tiempo Real**: Seguimiento de sesiones de directo, evolución de espectadores (`viewer_snapshots`), actividad de chat por intervalo, ranking de chatters por sesión, crecimiento diario de seguidores y desglose consolidado de eventos (`stream_events`).
- **Agente IA Conversacional**: Asistente inteligente integrado alimentado por Google Gemini con _function calling_, sanitización contra _prompt injection_, selector de modelo en línea y límite de contexto configurable en código (`AGENT_CONTEXT_LIMIT`).
- **Persistencia Híbrida de Alto Rendimiento**: Gestión de esquema con Prisma ORM y consultas asíncronas nativas en Python mediante `asyncpg` con reconexión automática ante cortes de red.
- **Seguridad Criptográfica y MultiFernet**: Cifrado simétrico de tokens OAuth con rotación automática mediante `MultiFernet` (prioridad `ENCRYPTION_KEY` con fallback HKDF/PBKDF2/SHA-256 desde `TWITCH_CLIENT_SECRET`).

---

## Stack Tecnológico

- **Backend**: Python 3.14, [`TwitchIO v3.3.2`](https://twitchio.dev/), [`httpx`](https://www.python-httpx.org/) (gestión de paquetes y entorno con [`uv`](https://docs.astral.sh/uv/))
- **Linter, Formatter & Type Checker Python**: [`ruff`](https://docs.astral.sh/ruff/), [`pyrefly`](https://pyrefly.org/)
- **Frontend & Web Server**: HTML5, Vanilla CSS, JS ESM (Preact + HTM + Chart.js), [`Vite`](https://vitejs.dev/), [`Starlette`](https://www.starlette.io/), [`Uvicorn`](https://www.uvicorn.org/)
- **Gestión & Calidad Frontend**: Node.js v24, `pnpm` v12, `oxlint`, `eslint`, `prettier`, `typescript`
- **Base de Datos & ORM**: PostgreSQL, Prisma ORM v7, `asyncpg`

---

## Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/leo-kleis/bot-tv.git
cd bot-tv
```

### 2. Configurar variables de entorno

Copia la plantilla `.env.example` a `.env` y completa tus credenciales:

```bash
cp .env.example .env
```

### 3. Instalar dependencias y preparar el proyecto

```bash
# Instalar dependencias de Python
uv sync

# Instalar dependencias de Node/Frontend
pnpm install

# Compilar los bundles de frontend con Vite hacia src/bot_tv/web/dist/
pnpm run build

# Aplicar migraciones o empujar el esquema de Prisma en PostgreSQL
pnpm run prisma:push
```

### 4. Vincular cuentas de Twitch (OAuth Setup)

Ejecuta el asistente interactivo para autorizar la cuenta del Bot y la cuenta del Canal (Broadcaster) mediante OAuth Device Code Flow (DCF):

```bash
uv run bot-setup
```

---

## Ejecución

### Modo Estándar (Backend + Frontend Compilado)

Inicia el servidor Web + Bot de Twitch (tanto `bot-tv` como `bot-web` apuntan al entrypoint unificado):

```bash
uv run bot-tv
# o equivalentemente:
uv run bot-web
```

El servidor web Starlette cargará la interfaz compilada desde `src/bot_tv/web/dist/`. Si el bundle no estuviese compilado, `_ensure_frontend_dist()` emitirá una advertencia informativa en logs y realizará fallback automático a `src/bot_tv/web/static/` sin interrumpir el arranque ASGI.

### Modo Desarrollo Frontend (Vite HMR)

Para iterar en componentes de interfaz con recarga instantánea:

```bash
# Terminal 1: Servidor ASGI backend
uv run bot-tv

# Terminal 2: Vite Dev Server (puerto 5173)
pnpm dev
```

Vite redirige transparentemente las rutas `/api` y `/ws` al backend en el puerto `8080`, mientras que el middleware ASGI permite el origen `http://localhost:5173` cuando `APP_ENV=development`.

### HTTPS Local para PWA en Móvil / LAN

Si colocas tus certificados en el directorio `certs/` (con nombres terminados en `-key.pem` y `.pem`, por ejemplo generados con `mkcert` para la IP local de tu máquina), Uvicorn habilitará TLS automáticamente en modo `development` (`https://<ip-local>:8080`), permitiendo instalar la PWA en dispositivos móviles sin advertencias de seguridad.

### Autenticación Web y PWA

Si defines `WEB_ACCESS_TOKEN` en `.env`:

- Accede mediante `https://<ip-host>:8080/?token=TU_TOKEN`.
- El middleware valida el token, establece una cookie de sesión `HttpOnly; SameSite=Lax` y redirige a la URL limpia sin parámetros, impidiendo que el token quede expuesto en el historial.
- Las rutas `/api/health`, `/manifest.json`, `/sw.js`, `/favicon.ico` e iconos quedan exentas para posibilitar la instalación nativa como PWA.

---

## Calidad de Código y Formateo

```bash
# Linter y chequeo de estilo en Python
uv run ruff check
uv run ruff format --check

# Chequeo estático de tipos en Python
uv run pyrefly check --min-severity warn

# Linters de frontend (oxlint + eslint)
pnpm run lint

# Chequeo de formateo en frontend (prettier)
pnpm run format:check

# Chequeo estático de tipos en TypeScript/JSDoc
pnpm run typecheck
```

---

## Estructura del Proyecto

```
bot-tv/
├── .agents/                 # Reglas de arquitectura, diseño web y accesibilidad
├── docs/                    # Documentación técnica
│   ├── database.md          # Arquitectura híbrida y modelos de datos
│   ├── deployment.md        # Guía de despliegue Cloud (scale-to-zero + HTTPS)
│   └── features.md          # Herramientas y funcionalidades de la app
├── extra/                   # Scripts auxiliares de diagnóstico y migración
├── prisma/                  # Esquema Prisma y migraciones SQL
│   ├── migrations/
│   └── schema.prisma
├── src/
│   └── bot_tv/
│       ├── actions/         # Lógica de acciones, clips y moderación
│       ├── agent/           # Integración con Google Gemini AI y herramientas
│       ├── components/      # Componentes modulares y oyentes EventSub
│       ├── database/        # Repositorios y capas de datos (asyncpg)
│       ├── utils/           # Utilidades de red, seguridad, env y logging
│       ├── web/             # Servidor Starlette/Uvicorn y Dashboard Web (PWA)
│       │   ├── api/         # Endpoints REST modulares
│       │   ├── dist/        # Bundle frontend generado por Vite (producción/local)
│       │   ├── static/      # Código fuente frontend (Preact, HTM, CSS, PWA)
│       │   ├── server.py    # Configuración de app Starlette y middlewares ASGI
│       │   └── ws_handler.py# Manejador de conexiones WebSocket y eventos
│       ├── bot.py           # Instancia principal del Bot (TwitchIO)
│       ├── irc.py           # Conexión IRC de Twitch para presencia de sala
│       ├── main.py          # Entrypoint unificado de la Aplicación Web (bot-tv / bot-web)
│       └── setup.py         # Entrypoint setup OAuth DCF (bot-setup)
├── Dockerfile               # Configuración de contenedor para despliegue
├── .env.example             # Plantilla de variables de entorno
├── package.json             # Manifiesto y scripts Node.js (v1.0.0-beta.1)
├── pyproject.toml           # Configuración del proyecto Python (v1.0.0b1)
└── vite.config.js           # Configuración de compilación y bundling Vite
```

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
