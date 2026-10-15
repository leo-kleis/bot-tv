---
trigger: always_on
glob: src/bot_tv/web/static/**
description: Reglas obligatorias de diseño responsivo, layout, profundidad (z-index), accesibilidad (WCAG 2.2), ergonomía y overlays para la interfaz web.
---

# Sistema de Diseño, Arquitectura Web y Accesibilidad — Reglas Obligatorias

## 1. Media Queries: Exclusividad Mutua

Los breakpoints de layout (aquellos que definen `display: grid/flex`, orientación de paneles y estructura de filas/columnas) deben ser **mutuamente excluyentes**. Si dos media queries pueden activarse simultáneamente, el que se carga después sobreescribe al anterior de manera silenciosa e impredecible.

Breakpoints oficiales del proyecto:

| Escenario | Condición | Layout General |
|---|---|---|
| Mobile portrait | `(max-width: 600px) and (min-height: 481px)` | Flex column (`header` → `content` → `tab-bar`) |
| Landscape | `(max-height: 480px)` | Grid 2 filas (`header` horizontal + `sidebar`/`content`) |
| Desktop/Tablet | `(min-width: 601px) and (min-height: 481px)` | Grid 3 filas (`header` + `tab-bar` + `content`) |

### Reglas para consultas secundarias e intermedias:
- **Consultas por ancho intermedio en componentes** (por ejemplo `max-width: 1480px`, `1050px`, `768px`): Si alteran el layout estructural o columnas de grilla, **DEBEN** incluir siempre `and (min-height: 481px)` para no colisionar con el escenario Landscape.
- **Landscape en dispositivos modernos**: Los teléfonos inteligentes modernos en posición horizontal superan casi invariablemente los 600px de ancho (típicamente entre 667px y 932px). Por tanto, las reglas de landscape móvil no deben asumir un `max-width: 600px`. El eje determinante de landscape es estrictamente `(max-height: 480px)`.
- **Excepción**: Reglas que no definen layout (como ocultar iconos accesorios o ajustar colores) pueden usar media queries simples sin exclusividad.

---

## 2. Grid con `fr`: Cálculo de Anchos Mínimos

Antes de definir breakpoints para un grid con unidades `fr`, calcular el ancho real que obtiene cada columna en el **límite inferior** del rango:

```
ancho_columna = (viewport - scrollbar - padding_contenedor - padding_grid - gaps - borders) / total_fr
```

- Controles intrínsecos como `input[type="date"]` requieren un mínimo de ~140–150px.
- Controles de texto `input[type="text"]` requieren al menos ~100px.
- Selectores personalizados `CustomSelect` requieren al menos ~120px.

El breakpoint debe activarse **antes** de que cualquier columna caiga por debajo del mínimo funcional de sus hijos. Es obligatorio agregar `min-width: 0` a los hijos directos del grid como red de seguridad contra desbordamientos.

---

## 3. Estructura de Pestañas y Componentes de Tab

Todo componente que se renderice dentro de `.tab-content` debe respetar la estructura de contención y flexión:

```css
.mi-tab {
  height: 100%;        /* Llenar el contenedor */
  display: flex;
  flex-direction: column;
  overflow: hidden;     /* Evitar desbordamiento externo */
}

.mi-tab-scrollable {
  flex: 1;             /* Ocupar todo el espacio vertical disponible */
  min-height: 0;       /* Permitir contracción en flex */
  overflow-y: auto;    /* Scroll interno único */
}

.mi-tab-fixed-bottom {
  flex-shrink: 0;      /* Inmunidad a contracción para barras de entrada y acciones */
}
```

**Verificación obligatoria**: Probar cualquier vista nueva en los 3 escenarios oficiales de layout confirmando que `.tab-content` no deje huecos vacíos ni genere scrollbars duplicados en el body.

---

## 4. Landscape (`max-height: 480px`) y Ergonomía Móvil

En landscape el espacio vertical es altamente restringido (~374px disponibles tras el header):

- **Paddings y espaciados**: Reducir paddings internos a 6–8px (evitar 12–16px) y gaps entre 4–8px.
- **Piso tipográfico mínimo absoluto**: Queda estrictamente prohibido usar fuentes menores a **11px** en cualquier contexto de la aplicación (prohibido `8px`, `9px`, `10px`). La escala para metadatos secundarios debe mantenerse legible.
- **Textareas e inputs**: Usar padding vertical mínimo (6–8px).
- **Empty states**: Utilizar versiones compactas (iconos pequeños <= 28px, espaciados contenidos).

---

## 5. Accesibilidad Universal y Navegación por Teclado (WCAG 2.2)

### Reglas Prohibitivas de Foco
1. **PROHIBIDO el uso de `outline: none` o `outline: 0`** en elementos interactivos sin declarar inmediatamente un reemplazo robusto mediante la pseudo-clase `:focus-visible`.
2. **PROHIBIDO depender exclusivamente de `box-shadow` para el estado de foco**. Los navegadores suprimen `box-shadow` en modos de contraste forzado (Windows High Contrast Mode). El foco visible debe emplear siempre `outline` con el token del sistema (`--focus-ring`).

### Estándares de Foco y Teclado
- Todo elemento accionable (`button`, `a`, `input`, `select`, `textarea`, `[role="button"]`, `[tabindex]`) debe implementar:
  ```css
  elemento:focus-visible {
    outline: var(--focus-ring);
    outline-offset: var(--focus-offset);
  }
  ```
- El contorno de foco debe mantener un contraste mínimo de 3:1 respecto a su fondo adyacente.
- El orden secuencial de foco con `Tab` debe ser natural y nunca quedar atrapado en elementos cerrados o transparentes.

### Objetivos Táctiles y Dimensiones (Touch Target Size)
- **Tamaño recomendado en móvil**: El área táctil interactiva debe alcanzar al menos **44 × 44px** (mediante padding o pseudo-elementos invisibles `::after`).
- **Piso mínimo absoluto (WCAG 2.2 SC 2.5.8)**: Ningún control interactivo operable puede tener un área efectiva inferior a **24 × 24px**, salvo enlaces inline en prosa continua.
- Queda prohibido definir botones interactivos con alturas físicas de 14–18px sin proporcionar un contenedor o pseudo-área que satisfaga el piso de 24px.

### Semántica ARIA y WAI-ARIA
- **Pestañas (`tablist`)**: Los botones con `role="tab"` deben tener `aria-selected` dinámico, `aria-controls` vinculado al panel correspondiente y responder a las teclas de dirección (flechas izquierda/derecha o arriba/abajo) según el patrón WAI-ARIA. Los paneles deben tener `role="tabpanel"` y `aria-labelledby`.
- **Selectores personalizados (`CustomSelect`)**: Deben cumplir el patrón WAI-ARIA Listbox:
  - Disparador con `aria-haspopup="listbox"`, `aria-expanded` y etiqueta accesible.
  - Lista con `role="listbox"` y opciones con `role="option"`, `aria-selected` y navegación por teclado con flechas, Enter y Escape.
- **Notificaciones y Toasts**:
  - Reservar `role="alert"` y `aria-live="assertive"` únicamente para fallos críticos, pérdidas de conexión o datos.
  - Para notificaciones operativas estándar (éxito, guardado, actualización), utilizar `role="status"` y `aria-live="polite"` para evitar cortar agresivamente la voz del lector de pantalla.

---

## 6. Overlays, Modales, Drawers y Aislamiento (`inert`)

1. **Aislamiento del fondo con `inert`**: Al desplegar un modal o drawer lateral con backdrop oscuro, el contenedor raíz de la página (`#app-root`) debe marcarse con el atributo `inert` o el modal debe utilizar la etiqueta nativa `<dialog>` con el método `.showModal()`. Esto asegura que el árbol de accesibilidad y el teclado no puedan acceder a controles fuera de la capa modal.
2. **Gestión de Foco (Focus Management)**:
   - **Apertura**: Al abrirse el overlay, el foco debe trasladarse de forma inmediata al primer elemento interactivo del diálogo (o al botón de cierre / input inicial).
   - **Cierre**: Al cerrarse, el foco **debe restaurarse** al control que detonó la apertura original.
   - **Escape**: La tecla `Escape` debe cerrar cualquier modal, drawer o menú desplegable abierto de forma prioritaria.
3. **Semántica de diálogo**: Todo modal o drawer debe declarar `role="dialog"`, `aria-modal="true"` y estar asociado a un título visible mediante `aria-labelledby`.

---

## 7. Movimiento Reducido y Modos de Visualización del Sistema

1. **Movimiento Reducido (`prefers-reduced-motion`)**:
   - Todo keyframe de animación continua (por ejemplo, pulsos `pulse-live`, animaciones continuas de radar) y transiciones estructurales superiores a `0.15s` deben quedar anulados o reducidos a opacidades inmediatas cuando el usuario active la preferencia de sistema:
     ```css
     @media (prefers-reduced-motion: reduce) {
       *, *::before, *::after {
         animation-duration: 0.01ms !important;
         animation-iteration-count: 1 !important;
         transition-duration: 0.01ms !important;
         scroll-behavior: auto !important;
       }
     }
     ```
2. **Modo de Contraste Forzado (`forced-colors: active`)**:
   - Elementos con bordes translúcidos (`border: rgba(...)`) o fondos oscuros con sombreado deben proveer contornos con palabras clave del sistema (`ButtonText`, `Highlight`, `CanvasText`) para mantenerse visibles en Windows High Contrast.
3. **Selección de Texto (`user-select`)**:
   - Está prohibido aplicar `user-select: none` de manera indiscriminada sobre el contenedor raíz `body`. La restricción de selección sólo debe aplicarse a elementos puntuales de control (botones, tabs, badges, select triggers). Tablas, registros, analíticas, mensajes y textos deben permanecer seleccionables.

---

## 8. Sistema de Profundidad Visual y Z-Index

### Reglas Prohibitivas
1. **PROHIBIDO usar valores numéricos mágicos directos** para capas flotantes/elevadas (`z-index: 9999`, `z-index: 2050`, `z-index: 1000`, etc.).
2. **PROHIBIDO inventar nuevas variables `--z-*`** sin actualizar la tabla oficial de capas en `variables.css` y en este documento.
3. **PROHIBIDO usar `z-index` en elementos estáticos** (`position: static`). El atributo sólo aplica en elementos posicionados (`relative`, `absolute`, `fixed`, `sticky`) o flex/grid items.

### Tabla Oficial de Capas (Stacking Layers)

Todos los componentes deben acoplarse estrictamente a las variables CSS de la tabla:

| Capa | Variable CSS | Valor | Uso permitido |
|---|---|---|---|
| In-card local | (numérico `1` al `5`) | `1` - `5` | Iconos de input, elementos internos de tarjetas, overlays de carga integrados en tablas. |
| Floating Controls | `--z-floating` | `20` | Botones flotantes dentro de contenedores (`.scroll-bottom-btn`). |
| Dropdown Wrapper | `--z-dropdown-wrap` | `30` | Contenedor o card padre que alberga un dropdown activo (`.custom-select-wrap.open`). |
| Dropdowns | `--z-dropdown` | `40` | Listas desplegables de selectores (`.custom-select-dropdown`). |
| Tab Bar | `--z-tab-bar` | `100` | Barra de pestañas principal (`.tab-bar`). |
| Header | `--z-header` | `110` | Cabecera superior fija (`.app-header`). |
| IRC Drawer | `--z-irc-drawer` | `300` | Panel lateral deslizable de chat/usuarios (`.irc-panel`). |
| History Drawer | `--z-history-drawer` | `400` | Panel lateral principal de historial (`.history-drawer`). |
| Overlays / Backdrops | `--z-overlay` | `500` | Telón de fondo oscuro/difuminado de modales o drawers (`.history-backdrop`). |
| Popovers | `--z-popover` | `520` | Popovers contextuales fixed (`.conn-popover`). |
| Modales | `--z-modal` | `610` | Diálogos modales de confirmación (`.modal-backdrop`). |
| Modal Dropdowns | `--z-modal-dropdown` | `620` | Menús desplegables y popovers activados dentro de diálogos modales en portales (`.category-dropdown-list`). |
| Toasts | `--z-toast` | `700` | Contenedor global de notificaciones toast (`.toast-container`). |

### Principios de Contexto de Apilamiento (Stacking Context)
- Si un componente contiene un `--z-dropdown`, su contenedor padre DEBE elevar su orden visual mediante `z-index: var(--z-dropdown-wrap)` o usar `isolation: isolate` para evitar que quede recortado por `overflow: hidden` de contenedores hermanos.
- `z-index` se mantiene compacto (< 1000). Nunca usar escalamiento arbitrario.
- Los Toasts (`700`) siempre se posicionan en la capa superior absoluta para garantizar visibilidad ante errores críticos.
