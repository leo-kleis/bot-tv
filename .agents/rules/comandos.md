# Comandos

## Proyecto (Ejecución)
- `uv run bot-tv` (Inicia el bot)
- `uv run bot-setup` (Ejecuta el script de configuración de Tokens)

## Consola Interactiva (durante la ejecución del bot)
- `sync_followers` (Sincroniza seguidores de todos los canales)
- `is_bot <usuario>` (Marca/desmarca un usuario como bot)
- `apodo <usuario> [apodo]` (Asigna o elimina un apodo; sin apodo lo elimina)
- `help` (Muestra los comandos disponibles)
- `exit` (Apaga el bot de forma limpia)

## Mise
- `mise install`
- `mise use python@3.14`
- `mise exec -- uv sync`
- `mise exec -- uv run <comando>`

## Uv (Gestor de dependencias)
- `uv sync` (Instala dependencias)
- `uv add <paquete>` (Añade una dependencia)
- `uv add --dev <paquete>` (Añade una dependencia de desarrollo)
- `uv remove <paquete>` (Elimina un paquete)
- `uv run <comando>` (Ejecuta un comando en el entorno virtual)

## Ruff (Linter & Formatter)
- `uv run ruff check .` (Revisa problemas)
- `uv run ruff check --fix .` (Autocorrige problemas)
- `uv run ruff format .` (Formatea el código)

## Pyrefly (Type Checker)
- `uv run pyrefly check` (Revisa tipos de forma estricta)
- `uv run pyrefly check --min-severity warn` (Revisa tipos y muestra advertencias)

## Prettier (Formatter)
- `pnpm run format` (Formatea archivos de frontend)
- `pnpm run format:check` (Verifica el formato de archivos de frontend)
- `pnpm exec prettier --write <ruta>` (Formatea una ruta específica)

## Oxlint (Linter rápido)
- `pnpm exec oxlint <ruta>` (Analiza problemas en una ruta específica)
- `pnpm exec oxlint --fix <ruta>` (Corrige problemas automáticamente en una ruta específica)

## Eslint (Linter detallado)
- `pnpm exec eslint <ruta>` (Analiza problemas en una ruta específica)
- `pnpm exec eslint --fix <ruta>` (Corrige problemas automáticamente en una ruta específica)

## Scripts de Frontend (Linter & Formatter combinados)
- `pnpm run lint` (Ejecuta oxlint y eslint en el directorio static)
- `pnpm run lint:fix` (Ejecuta oxlint y eslint con corrección automática en el directorio static)

## Prisma (Gestión de Base de Datos)
- `pnpm run prisma:migrate -- --name <nombre>` (Crea y aplica una nueva migración en PostgreSQL basándose en los cambios de schema.prisma)
- `pnpm run prisma:push` (Sincroniza directamente el esquema schema.prisma con la base de datos en la nube sin crear historial de migraciones)
- `pnpm run prisma:status` (Comprueba el estado del historial de migraciones de la base de datos)


