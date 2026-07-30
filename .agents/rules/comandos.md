# Comandos

## Proyecto (Ejecución)

- Inicia el bot:
  ```bash
  uv run bot-tv
  ```
- Ejecuta el script de configuración de Tokens:
  ```bash
  uv run bot-setup
  ```

## Consola Interactiva (durante la ejecución del bot)

- Sincroniza seguidores de todos los canales:
  ```bash
  sync_followers
  ```
- Marca/desmarca un usuario como bot:
  ```bash
  is_bot <usuario>
  ```
- Asigna o elimina un apodo (sin apodo lo elimina):
  ```bash
  apodo <usuario> [apodo]
  ```
- Muestra los comandos disponibles:
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

- Instala dependencias:
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

- Revisa problemas:
  ```bash
  uv run ruff check .
  ```
- Autocorrige problemas:
  ```bash
  uv run ruff check --fix .
  ```
- Formatea el código:
  ```bash
  uv run ruff format .
  ```

## Pyrefly (Type Checker)

- Revisa tipos de forma estricta:
  ```bash
  uv run pyrefly check
  ```
- Revisa tipos y muestra advertencias:
  ```bash
  uv run pyrefly check --min-severity warn
  ```

## Prettier (Formatter)

- Formatea archivos de frontend:
  ```bash
  pnpm run format
  ```
- Verifica el formato de archivos de frontend:
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

## Scripts de Frontend (Linter & Formatter combinados)

- Ejecuta oxlint y eslint en el directorio static:
  ```bash
  pnpm run lint
  ```
- Ejecuta oxlint y eslint con corrección automática en el directorio static:
  ```bash
  pnpm run lint:fix
  ```

## Prisma (Gestión de Base de Datos)

- Crea y aplica una nueva migración en PostgreSQL basándose en los cambios de schema.prisma:
  ```bash
  pnpm run prisma:migrate -- --name <nombre>
  ```
- Sincroniza directamente el esquema schema.prisma con la base de datos en la nube sin crear historial de migraciones:
  ```bash
  pnpm run prisma:push
  ```
- Comprueba el estado del historial de migraciones de la base de datos:
  ```bash
  pnpm run prisma:status
  ```

## Lefthook (Git Hooks)

- Instala y activa los Git hooks locales en el repositorio mediante la versión gestionada por mise:
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

- Incrementa la versión parche, ej. 0.6.1 a 0.6.2, crea el commit, tag de Git y sube todo a GitHub:
  ```bash
  pnpm run release patch
  ```
- Incrementa la versión menor, ej. 0.6.1 a 0.7.0, crea commit, tag y push:
  ```bash
  pnpm run release minor
  ```
- Incrementa la versión mayor, ej. 0.6.1 a 1.0.0, crea commit, tag y push:
  ```bash
  pnpm run release major
  ```
- Simula el proceso de lanzamiento mostrando el diff y los comandos a ejecutar sin aplicarlos:
  ```bash
  pnpm run release -- --dry-run
  ```
