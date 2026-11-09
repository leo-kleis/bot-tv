# Reglas de Versionado y Renovación de Archivos en Clientes (SemVer 2.0.0)

Especificación de referencia: https://semver.org/lang/es/

## 1. Fuente única de verdad

- La versión vigente se declara en `package.json` (`"version"`), que es la que consumen el build de Vite y el Service Worker.
- `pyproject.toml` (`version`) debe coincidir. `pnpm release` (`release-it`, ver `.release-it.json`) actualiza ambos en un solo paso y crea el tag `v<versión>`. Está prohibido editar la versión a mano en un solo archivo.
- Formato: `MAYOR.MENOR.PARCHE[-prelanzamiento][+metadatos]`, sin ceros a la izquierda.
  - `package.json` usa la notación SemVer (`1.0.0-beta.1`); `pyproject.toml` la normaliza a PEP 440 (`1.0.0b1`). Son la misma versión.

## 2. Cuándo incrementar cada número

| Número | Se incrementa cuando | Ejemplo en este proyecto |
|---|---|---|
| MAYOR | Cambios incompatibles en la API pública | Cambiar el contrato de `/api/*` o del protocolo WebSocket, o un cambio de esquema de BD no reversible |
| MENOR | Funcionalidad nueva compatible, o algo marcado como obsoleto | Nueva pestaña, nuevo endpoint, nuevo evento |
| PARCHE | Corrección de errores compatible | Arreglo de UI, de caché, de un endpoint |

- Al subir MAYOR, MENOR y PARCHE vuelven a `0`; al subir MENOR, PARCHE vuelve a `0`.
- Una versión publicada es inmutable: cualquier corrección posterior exige una versión nueva.
- Versiones `0.y.z` son de desarrollo inicial; `1.0.0` define la API pública estable.
- Prelanzamientos (`-alpha.N`, `-beta.N`, `-rc.N`) tienen menor precedencia que la versión final. Los metadatos `+...` no cuentan para la precedencia.

## 3. Cómo la versión fuerza la renovación en la PWA

1. `vite.config.js` lee `version` de `package.json` y, al compilar, reemplaza el marcador `__APP_VERSION__` de `src/bot_tv/web/static/sw.js` al copiarlo a `dist/sw.js`.
2. Si la versión cambia, cambian los bytes de `sw.js`. El navegador compara `sw.js` byte a byte en cada navegación y, si difiere, instala el nuevo Service Worker.
3. En `activate`, el nuevo SW borra toda caché cuyo nombre empiece por `bot-tv-` y no sea `bot-tv-<versión vigente>`, y luego toma el control (`clients.claim()`).

Esto se complementa con:
- Bundles de Vite con hash en el nombre (`assets/index-<hash>.js`): cada build genera URLs nuevas.
- `Cache-Control: no-cache` en `/`, `/sw.js` y `/manifest.json` (`src/bot_tv/web/server.py`), para que el navegador siempre revalide el HTML y el SW.

## 4. Reglas obligatorias

- Si se agrega almacenamiento en caché al Service Worker (Cache Storage), el nombre de la caché DEBE ser `CURRENT_CACHE` (`bot-tv-<APP_VERSION>`). Nunca usar nombres fijos ni hashes manuales.
- No registrar nunca `sw.js` con una URL versionada (`/sw.js?v=...`): la versión viaja dentro del contenido.
- `sw.js` y `index.html` NUNCA se sirven con `max-age` ni `immutable`.
- Todo cambio que afecte lo que el cliente descarga y deba llegar a los móviles instalados requiere un release (al menos PARCHE), porque sin cambio de versión el contenido de `sw.js` no cambia.
- No modificar el marcador `__APP_VERSION__` en el código fuente: solo el build lo sustituye.
