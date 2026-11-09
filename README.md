[![Version](https://img.shields.io/badge/version-1.0.0--beta.1-8b5cf6?style=flat-square)](#)
[![Python](https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![TwitchIO](https://img.shields.io/badge/twitchio-v3.3.2-9146FF?style=flat-square&logo=twitch&logoColor=white)](https://twitchio.dev/)
[![Node.js](https://img.shields.io/badge/node.js-v24.12.0-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![uv](https://img.shields.io/badge/uv-0.12.21-DE5D43?style=flat-square)](https://docs.astral.sh/uv/)
[![pnpm](https://img.shields.io/badge/pnpm-v11.15.0-F69220?style=flat-square&logo=pnpm&logoColor=white)](https://pnpm.io/)
[![Prisma](https://img.shields.io/badge/prisma-v7.9.1-2D3748?style=flat-square&logo=prisma&logoColor=white)](https://www.prisma.io/)
[![License](https://img.shields.io/badge/license-MIT-4ba51c?style=flat-square)](LICENSE)

Aplicación Web interactiva (PWA) y Bot de Twitch con integración de Inteligencia Artificial (Google Gemini), arquitectura *event-driven*, analíticas de transmisión en tiempo real y persistencia híbrida en PostgreSQL (Prisma + `asyncpg`).

- Para una descripción detallada de todas las herramientas, endpoints y funcionalidades del sistema, consulta [docs/features.md](docs/features.md).
- Para el modelo relacional y flujo de migraciones, consulta [docs/database.md](docs/database.md).
- Para desplegar la aplicación en la nube con **HTTPS** y **encendido bajo demanda (scale-to-zero)**, consulta [docs/deployment.md](docs/deployment.md).

---

## Características (`v1.0.0-beta.1`)

- **Dashboard Web & PWA Unificado**: Panel de administración visual en tiempo real adaptable a escritorio, tablet y móvil (vertical y horizontal) con soporte de instalación PWA.
- **Integración Twitch IRC y EventSub**: Conexión nativa con TwitchIO para responder comandos, moderar el chat, crear clips y capturar eventos del canal.
- **Analíticas de Stream en Tiempo Real**: Seguimiento de sesiones de directo, evolución de espectadores (`viewer_snapshots`), actividad de chat, crecimiento de seguidores y desglose de eventos (`stream_events`).
- **Agente IA Conversacional**: Asistente inteligente integrado alimentado por Google Gemini con *function calling*, sanitización contra *prompt injection* y *rate limiting* con *fallback* automático.
- **Persistencia Híbrida de Alto Rendimiento**: Gestión de esquema con Prisma ORM y consultas asíncronas nativas en Python mediante `asyncpg` con reconexión automática ante cortes de red.

---

## Stack Tecnológico

- **Backend**: Python 3.14, [`TwitchIO v3.3.2`](https://twitchio.dev/), [`httpx`](https://www.python-httpx.org/) (gestión con [`uv`](https://docs.astral.sh/uv/))
- **Linter, Formatter & Type Checker Python**: [`ruff`](https://docs.astral.sh/ruff/), [`pyrefly`](https://pyrefly.org/)
- **Frontend & Web Server**: HTML5, Vanilla CSS, JS ESM (Preact + HTM + Chart.js), [`Starlette`](https://www.starlette.io/), [`Uvicorn`](https://www.uvicorn.org/)
- **Gestión & Calidad Frontend**: Node.js, `pnpm`, `oxlint`, `eslint`, `prettier`
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

### 3. Instalar dependencias y sincronizar esquema
```bash
# Instalar dependencias de Python
uv sync

# Instalar dependencias de Node/Frontend
pnpm install

# Aplicar migraciones o empujar el esquema de Prisma
pnpm run prisma:push
```

### 4. Vincular cuentas de Twitch (OAuth Setup)
Ejecuta el asistente interactivo para autorizar la cuenta del Bot y la cuenta del Canal (Broadcaster) mediante OAuth Device Code Flow (DCF):
```bash
uv run bot-setup
```

---

## Ejecución

Inicia el servidor Web + Bot de Twitch (tanto `bot-tv` como `bot-web` apuntan al entrypoint unificado):
```bash
uv run bot-tv
# o equivalentemente:
uv run bot-web
```

- **Modo Red Local con HTTPS (PWA Móvil)**: Si existen certificados en `certs/cert.pem` y `certs/key.pem`, Uvicorn levanta automáticamente con TLS (`https://<ip-local>:8080`).
- **Modo Nube / Contenedor**: Respeta automáticamente las variables `PORT` / `WEB_PORT` y cabeceras de proxy inverso (`X-Forwarded-Proto`) para funcionar detrás de balanceadores HTTPS.

---

## Calidad de Código y Formateo

```bash
# Linter y chequeo de estilo en Python
uv run ruff check
uv run ruff format --check

# Chequeo de tipos en Python
uv run pyrefly check

# Linters frontend (oxlint + eslint)
pnpm run lint

# Chequeo de formateo en frontend
pnpm run format:check
```

---

## Estructura del Proyecto

```
bot-tv/
├── .agents/                 # Reglas de diseño, accesibilidad y base de datos
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
│       ├── utils/           # Utilidades de red, seguridad y formato
│       ├── web/             # Servidor Starlette/Uvicorn y Dashboard Web (PWA)
│       ├── bot.py           # Instancia principal del Bot (TwitchIO)
│       ├── irc.py           # Conexión IRC de Twitch para presencia de sala
│       ├── main.py          # Entrypoint unificado de la Aplicación Web (bot-tv / bot-web)
│       └── setup.py         # Entrypoint setup OAuth DCF (bot-setup)
├── Dockerfile               # Imagen de contenedor para despliegue en la nube
├── .env.example             # Plantilla de variables de entorno
├── package.json             # Manifiesto y scripts Node.js (v1.0.0-beta.1)
└── pyproject.toml           # Configuración del proyecto Python (v1.0.0b1)
```

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
