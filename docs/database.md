# Documentación de la Base de Datos

Este documento describe la arquitectura de la base de datos de **bot-tv**, su diseño relacional y el flujo de trabajo para realizar modificaciones en el esquema.

---

## 1. Arquitectura Híbrida

El proyecto utiliza una arquitectura de base de datos dividida:

1. **Gestión del Esquema y Migraciones (Prisma v7):**
   Toda la estructura física de la base de datos (tablas, claves primarias, claves foráneas e índices) se define y gestiona en el archivo [schema.prisma](file:///c:/Users/Leo/Repo/bot-tv/prisma/schema.prisma) usando TypeScript/Node.js localmente.
   
2. **Ejecución y Consultas en Producción (Python + `asyncpg`):**
   El bot de Python se conecta de forma directa a PostgreSQL mediante la librería `asyncpg` y ejecuta sentencias SQL en bruto (raw queries) de alto rendimiento. Las migraciones automáticas en Python han sido desactivadas para centralizar el esquema en Prisma.

---

## 2. Modelos de la Base de Datos

### Tabla: `users`
Almacena la información global de los usuarios que interactúan con el bot.
- `user_id` (TEXT, PK): ID único de usuario de Twitch.
- `username` (TEXT): Nombre de usuario.
- `display_name` (TEXT): Nombre para mostrar en el chat.
- `nickname` (TEXT): Apodo personalizado asignado en el bot.
- `is_bot` (BOOLEAN): Indica si la cuenta es un bot.
- `profile_image_url` (TEXT): URL de la imagen de perfil.

### Tabla: `channel_users`
Representa la relación de cada usuario con cada canal en el que el bot está activo, incluyendo su seguimiento y roles específicos del canal.
- `channel_id` (TEXT, PK): ID del canal (broadcaster) al que pertenece el usuario.
- `user_id` (TEXT, PK, FK): ID del usuario que apunta a `users.user_id`.
- `followed_at` (TEXT): Fecha y hora en la que comenzó a seguir.
- `unfollowed_at` (TEXT): Fecha y hora en la que dejó de seguir.
- `is_moderator` (BOOLEAN): Indica si es moderador en este canal específico.
- `is_vip` (BOOLEAN): Indica si tiene rango VIP en este canal específico.
- `is_subscriber` (BOOLEAN): Indica si está suscrito a este canal específico.
- `sub_tier` (TEXT): Nivel de suscripción ("1000" | "2000" | "3000").
- `gifter_id` (TEXT): ID de usuario de quien regaló la suscripción.
- **Relación:** Relación de **uno a muchos (1:n)** desde `users` a `channel_users`. Un usuario en `users` tiene roles y seguimiento independientes por cada canal.

### Tabla: `chat_history`
Almacena el historial de mensajes de los canales.
- `id` (UUID, PK): Identificador único del mensaje.
- `channel_id` (TEXT): ID del canal donde se escribió el mensaje.
- `user_id` (TEXT, FK): ID del usuario que envió el mensaje (`users.user_id`).
- `message` (TEXT): Contenido del mensaje de chat.
- `timestamp` (TEXT): Marca de tiempo del mensaje.

### Tabla: `tokens`
Persistencia de tokens OAuth encriptados simétricamente con Fernet.
- `user_id` (TEXT, PK): ID de Twitch.
- `username` (TEXT): Nombre de usuario.
- `token` (TEXT): Access token encriptado.
- `refresh` (TEXT): Refresh token encriptado.

### Tabla: `app_settings`
Configuraciones clave-valor globales de la aplicación.
- `key` (TEXT, PK): Nombre de la configuración.
- `value` (TEXT): Valor de la configuración.

### Tabla: `api_consumption_log`
Historial de consumo del modelo LLM.
- `id` (BIGINT, PK, Autoincremental).
- `model` (TEXT): Nombre del modelo consumido.
- `timestamp` (DOUBLE PRECISION): Fecha y hora en formato Unix epoch.
- `type` (TEXT): Tipo de petición (ej. completion).

---

## 3. Flujo para modificar o agregar tablas/columnas

Cuando requieras realizar cambios en la base de datos (por ejemplo, añadir una tabla o una columna a una tabla existente):

### Paso 1: Modificar el esquema
Abre [schema.prisma](file:///c:/Users/Leo/Repo/bot-tv/prisma/schema.prisma) y realiza los cambios en los modelos correspondientes.

### Paso 2: Generar y aplicar la migración

#### A) En Entornos Interactivos (Tu Terminal Local)
Ejecuta el siguiente comando para generar y aplicar la migración de forma automática:
```bash
pnpm run prisma:migrate -- --name <nombre_descriptivo_de_migracion>
```
*Nota: Si el cambio implica potencial pérdida de datos, Prisma te pedirá confirmación en consola (interfaz interactiva).*

#### B) En Entornos No Interactivos (Agentes de IA o Pipelines CI/CD)
Dado que los agentes de IA o procesos automatizados carecen de una terminal interactiva (TTY) para responder preguntas o confirmar advertencias, se debe usar este flujo alternativo:
1. Crea la carpeta de la migración manualmente dentro de `prisma/migrations/` con la nomenclatura `<timestamp>_<nombre_migracion>`.
2. Crea el archivo `migration.sql` dentro de esa carpeta y escribe la sentencia SQL de alteración de manera directa.
3. Ejecuta el comando no interactivo:
   ```bash
   npx prisma migrate deploy
   ```
   Este comando leerá las migraciones creadas y las aplicará en la base de datos en la nube sin realizar preguntas en consola.

### Paso 3: Sincronizar en la aplicación de Python
Modifica las sentencias SQL en los archivos de repositorio en `src/bot_tv/database/repositories/` (ej. [user_repo.py](file:///c:/Users/Leo/Repo/bot-tv/src/bot_tv/database/repositories/user_repo.py)) para reflejar los nuevos campos o tablas.
