# Comandos

## Proyecto (Ejecución)
- `uv run bot-tv` (Inicia el bot)
- `uv run bot-setup` (Ejecuta el script de configuración de Tokens)

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
