[![Python](https://img.shields.io/badge/python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![TwitchIO](https://img.shields.io/badge/twitchio-v3.3.2-9146FF?style=flat-square&logo=twitch&logoColor=white)](https://twitchio.dev/)
[![Node.js](https://img.shields.io/badge/node.js-v24.12.0-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![uv](https://img.shields.io/badge/uv-0.12.21-DE5D43?style=flat-square)](https://docs.astral.sh/uv/)
[![pnpm](https://img.shields.io/badge/pnpm-v11.15.0-F69220?style=flat-square&logo=pnpm&logoColor=white)](https://pnpm.io/)
[![Prisma](https://img.shields.io/badge/prisma-v7.9.1-2D3748?style=flat-square&logo=prisma&logoColor=white)](https://www.prisma.io/)
[![License](https://img.shields.io/badge/license-MIT-4ba51c?style=flat-square)](LICENSE)

Bot interactivo de Twitch con integración de Inteligencia Artificial (Google Gemini), arquitectura event-driven, persistencia en PostgreSQL con Prisma y un Dashboard Web en tiempo real como interfaz predeterminada.

Para una descripción detallada de todas las herramientas, endpoints y funcionalidades del sistema, consulta [docs/features.md](docs/features.md).

---

## Características

- **Integración Twitch IRC y EventSub**: Conexión nativa con TwitchIO para responder comandos, procesar eventos y moderar el chat.
- **Agente IA Conversacional**: Asistente inteligente integrado alimentado por Google Gemini con capacidades de contexto y rate limiting.
- **Dashboard Web interactivo**: Panel de administración visual para monitoreo del chat, gestión de usuarios y configuración en tiempo real (interfaz predeterminada).
- **Persistencia Robusta**: Integración híbrida con PostgreSQL mediante Prisma ORM (migraciones) y `asyncpg` (consultas nativas de alto rendimiento).
- **Consola Terminal / CLI**: Interfaz interactiva de consola con autocompletado para administración local.

---

## Stack Tecnológico

- **Backend**: Python 3.14, [`TwitchIO v3.3.2`](https://twitchio.dev/) (gestión con [`uv`](https://docs.astral.sh/uv/))
- **Linter & Formatter Python**: [`ruff`](https://docs.astral.sh/ruff/)
- **Type Checker Python**: [`pyrefly`](https://pyrefly.org/)
- **Frontend & Web Server**: HTML5, Vanilla CSS, JS ESM (Preact), [`Starlette`](https://www.starlette.io/), [`Uvicorn`](https://www.uvicorn.org/)
- **Gestión Frontend**: Node.js, `pnpm`
- **Linter & Formatter Frontend**: `oxlint`, `eslint`, `prettier`
- **Base de Datos & ORM**: PostgreSQL, Prisma ORM, `asyncpg`
- **Herramientas de Entorno**: [`mise`](https://mise.jdx.dev/)

---

## Requisitos Previos

Asegúrate de contar con los siguientes administradores instalados en tu sistema:
- **`mise`** (Administrador de versiones y herramientas)
- **`uv`** (Gestor de paquetes y entornos Python)
- **`pnpm`** (Gestor de paquetes JavaScript)

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

Consulta los comentarios incluidos en `.env.example` para obtener instrucciones detalladas sobre dónde conseguir las credenciales de Twitch, la API Key de Gemini y la base de datos.

### 3. Instalar dependencias
```bash
# Instalar dependencias de Python
uv sync

# Instalar dependencias de Node/Frontend
pnpm install

# Generar cliente de Prisma
pnpm run prisma:push
```

### 4. Vincular cuentas de Twitch (OAuth Setup)
Ejecuta el asistente interactivo para autorizar la cuenta del Bot y la cuenta del Canal (Broadcaster) mediante OAuth Device Code Flow (DCF):
```bash
uv run bot-setup
```

---

## Ejecución

### Iniciar el Dashboard Web (Interfaz predeterminada)
```bash
uv run bot-web
```

### Iniciar en modo Consola Terminal / CLI
```bash
uv run bot-tv
```

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

# Chequeo de tipos TypeScript en scripts Prisma
pnpm run typecheck
```

---

## Estructura del Proyecto

```
bot-tv/
├── .agents/                 # Reglas y directivas de desarrollo
├── docs/                    # Documentación técnica
│   ├── database.md          # Arquitectura híbrida y modelos de datos
│   └── features.md          # Herramientas y funcionalidades de la app
├── extra/                   # Scripts auxiliares y utilidades
├── prisma/                  # Esquema Prisma y migraciones
│   ├── migrations/
│   └── schema.prisma
├── src/
│   └── bot_tv/
│       ├── actions/         # Lógica de acciones y moderación
│       ├── agent/           # Integración con Google Gemini AI y herramientas
│       ├── components/      # Componentes modulares y oyentes EventSub
│       ├── console/         # Consola interactiva REPL
│       ├── consumers/       # Consumidor de terminal y bus de eventos
│       ├── database/        # Repositorios y capas de datos (asyncpg)
│       ├── utils/           # Utilidades de red, seguridad y formato
│       ├── web/             # Servidor Starlette/Uvicorn y Dashboard Web (PWA)
│       ├── bot.py           # Instancia principal del Bot (TwitchIO)
│       ├── irc.py           # Conexión IRC de Twitch
│       ├── main.py          # Entrypoint consola CLI (bot-tv)
│       ├── setup.py         # Entrypoint setup OAuth DCF (bot-setup)
│       └── web_main.py      # Entrypoint servidor web (bot-web)
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Exclusiones de Git
├── lefthook.yml             # Hooks de Git (pre-commit)
├── package.json             # Manifiesto y scripts Node.js
└── pyproject.toml           # Configuración del proyecto Python
```

---

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
