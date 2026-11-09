# Comandos (`v1.0.0-beta.1` — 100% Web App & PWA)

## Proyecto (Ejecución y Entornos `development` vs `production`)

- Inicia el bot y el Dashboard Web en **modo Desarrollo Local (`APP_ENV=development` por defecto)** (habilita certificados `certs/*.pem` para LAN/PWA, *live-reload* de archivos estáticos, hasta 20 conexiones WS y sin auto-apagado por inactividad):
  ```bash
  uv run bot-tv
  # o su alias equivalente:
  uv run bot-web
  ```
- Inicia el bot y el Dashboard Web en **modo Producción (`APP_ENV=production`)** (pensado para Nube / Tailscale: caché de activos estáticos, cabeceras HSTS, máximo 3 clientes WS simultáneos y auto-apagado bajo demanda tras 300s sin usuarios conectados):
  ```bash
  APP_ENV=production uv run bot-tv
  ```
- Ejecuta el asistente interactivo de configuración inicial de tokens OAuth (Device Code Flow) y los persiste cifrados en PostgreSQL (Prisma Console):
  ```bash
  uv run bot-setup
  ```

## Mise

```bash
mise install
mise use python@3.14
mise exec -- uv sync
mise exec -- uv run <comando>
```

## Uv (Gestor de dependencias Python)

- Instala y sincroniza dependencias del proyecto:
  ```bash
  uv sync
  ```
- Añade una dependencia:
  ```bash
  uv add <paquete>
  ```
- Añade una dependencia de desarrollo:
  ```bash
  uv add --dev <paquete>
  ```
- Elimina un paquete:
  ```bash
  uv remove <paquete>
  ```
- Ejecuta un comando en el entorno virtual:
  ```bash
  uv run <comando>
  ```

## Ruff (Linter & Formatter Python)

- Analiza problemas de linting en el proyecto:
  ```bash
  uv run ruff check
  ```
- Analiza problemas en una ruta específica:
  ```bash
  uv run ruff check <ruta>
  ```
- Autocorrige problemas detectados:
  ```bash
  uv run ruff check --fix
  ```
- Formatea el código:
  ```bash
  uv run ruff format
  ```
- Verifica el formato sin modificar archivos:
  ```bash
  uv run ruff format --check
  ```

## Pyrefly (Type Checker Python)

- Revisa tipos en modo estándar (falla ante errores de tipo):
  ```bash
  uv run pyrefly check
  ```
- Revisa tipos en modo estricto (muestra advertencias y falla ante warnings y errores):
  ```bash
  uv run pyrefly check --min-severity warn
  ```

## Prettier (Formatter Frontend)

- Formatea archivos de frontend (`.js`, `.html`, `.css`):
  ```bash
  pnpm run format
  ```
- Verifica el formato de archivos de frontend sin modificar:
  ```bash
  pnpm run format:check
  ```
- Formatea una ruta específica:
  ```bash
  pnpm exec prettier --write <ruta>
  ```

## Oxlint & ESLint (Linters Frontend)

- Ejecuta `oxlint` y `eslint` en el directorio `static`:
  ```bash
  pnpm run lint
  ```
- Ejecuta `oxlint` y `eslint` con corrección automática:
  ```bash
  pnpm run lint:fix
  ```
- Valida tipos de TypeScript en el proyecto:
  ```bash
  pnpm run typecheck
  ```

## Vite (Bundler & Servidor de Desarrollo Frontend)

- Compila y empaqueta el frontend (`Preact` + `CSS` + `Chart.js`) hacia `src/bot_tv/web/dist/` (con *code splitting* y carga diferida de analíticas):
  ```bash
  pnpm run build
  ```
- Inicia el servidor de desarrollo de Vite con HMR y proxy hacia `127.0.0.1:8080`:
  ```bash
  pnpm run dev
  ```
- Previsualiza localmente el bundle de producción compilado:
  ```bash
  pnpm run preview
  ```

## Prisma (Gestión de Base de Datos en Prisma Console / PostgreSQL)

- Crea y aplica una nueva migración en desarrollo basándose en los cambios de `schema.prisma`:
  ```bash
  pnpm run prisma:migrate -- --name <nombre>
  ```
- Aplica las migraciones pendientes ya existentes en `prisma/migrations/` (sin prompts interactivos, ideal tras actualizar el repo o en producción):
  ```bash
  pnpm run prisma:deploy
  ```
- Sincroniza directamente el esquema `schema.prisma` con la base de datos sin crear historial de migraciones:
  ```bash
  pnpm run prisma:push
  ```
- Comprueba el estado del historial de migraciones de la base de datos:
  ```bash
  pnpm run prisma:status
  ```

## Lefthook (Git Hooks)

- Instala y activa los Git hooks locales en el repositorio:
  ```bash
  lefthook install
  ```
- Ejecuta manualmente las verificaciones de pre-commit en los archivos locales:
  ```bash
  lefthook run pre-commit
  ```
- Desactiva y remueve los Git hooks locales del repositorio:
  ```bash
  lefthook uninstall
  ```

## Release-it (Gestión de Versiones)

- Incrementa la versión parche, crea el commit, tag de Git y sube los cambios:
  ```bash
  pnpm run release patch
  ```
- Incrementa la versión menor, crea commit, tag y push:
  ```bash
  pnpm run release minor
  ```
- Incrementa la versión mayor, crea commit, tag y push:
  ```bash
  pnpm run release major
  ```
- Simula el proceso de lanzamiento mostrando el diff y los comandos a ejecutar sin aplicarlos:
  ```bash
  pnpm run release -- --dry-run
  ```

## Scripts Utilitarios (`extra/`)

- Valida los scopes configurados para los tokens de Twitch:
  ```bash
  uv run python extra/check_scopes.py
  ```
- Consulta o verifica IDs de Twitch:
  ```bash
  uv run python extra/check_twitch_id.py
  ```
- Obtiene IDs de canales y usuarios de Twitch:
  ```bash
  uv run python extra/get_twitch_ids.py
  ```
- Verifica la existencia y estructura de tablas en PostgreSQL:
  ```bash
  uv run python extra/run_migrations.py
  ```
