# Comandos

## Proyecto (Ejecución)

- Inicia el bot (modo terminal con consola interactiva):
  ```bash
  uv run bot-tv
  ```
- Inicia el bot y el dashboard web (servidor Uvicorn + TwitchIO):
  ```bash
  uv run bot-web
  ```
- Ejecuta el asistente de configuración inicial de tokens OAuth y suscripciones:
  ```bash
  uv run bot-setup
  ```

## Consola Interactiva (durante la ejecución de `bot-tv`)

- Sincroniza seguidores de todos los canales:
  ```bash
  sync_followers
  ```
- Marca o desmarca un usuario como bot:
  ```bash
  is_bot <usuario>
  ```
- Asigna o elimina un apodo (sin apodo lo elimina):
  ```bash
  apodo <usuario> [apodo]
  ```
- Pregunta o interactúa directamente con el asistente IA (Gemini):
  ```bash
  talk <mensaje>
  ```
- Muestra el estado del rate limiter (RPM/RPD del modelo actual o de todos):
  ```bash
  rpm [all]
  ```
- Muestra o cambia el modelo de IA activo en tiempo de ejecución:
  ```bash
  model [nombre]
  ```
- Lista todos los modelos disponibles en AI Studio y sus límites:
  ```bash
  models
  ```
- Muestra la lista de comandos disponibles:
  ```bash
  help
  ```
- Apaga el bot de forma limpia:
  ```bash
  exit
  ```

## Mise

```bash
mise install
mise use python@3.14
mise exec -- uv sync
mise exec -- uv run <comando>
```

## Uv (Gestor de dependencias)

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

## Ruff (Linter & Formatter)

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

## Pyrefly (Type Checker)

- Revisa tipos en modo estándar (falla ante errores de tipo):
  ```bash
  uv run pyrefly check
  ```
- Revisa tipos en modo estricto (muestra advertencias y falla ante warnings y errores):
  ```bash
  uv run pyrefly check --min-severity warn
  ```

## Prettier (Formatter)

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

## Oxlint (Linter rápido)

- Analiza problemas en una ruta específica:
  ```bash
  pnpm exec oxlint <ruta>
  ```
- Corrige problemas automáticamente en una ruta específica:
  ```bash
  pnpm exec oxlint --fix <ruta>
  ```

## Eslint (Linter detallado)

- Analiza problemas en una ruta específica:
  ```bash
  pnpm exec eslint <ruta>
  ```
- Corrige problemas automáticamente en una ruta específica:
  ```bash
  pnpm exec eslint --fix <ruta>
  ```

## Scripts de Frontend (Linter, Formatter & Typecheck)

- Ejecuta oxlint y eslint en el directorio static:
  ```bash
  pnpm run lint
  ```
- Ejecuta oxlint y eslint con corrección automática en el directorio static:
  ```bash
  pnpm run lint:fix
  ```
- Valida tipos de TypeScript en el proyecto:
  ```bash
  pnpm run typecheck
  ```

## Prisma (Gestión de Base de Datos)

- Crea y aplica una nueva migración en PostgreSQL basándose en los cambios de schema.prisma:
  ```bash
  pnpm run prisma:migrate -- --name <nombre>
  ```
- Sincroniza directamente el esquema schema.prisma con la base de datos sin crear historial de migraciones:
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
