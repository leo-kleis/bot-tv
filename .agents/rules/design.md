---
trigger: always_on
glob: src/bot_tv/web/static/**
description: Reglas de diseño responsivo y layout para la interfaz web. Previene conflictos de media queries, desbordamientos de grid y problemas de altura en pestañas.
---

# Diseño Responsivo — Reglas Obligatorias

## Media Queries: Exclusividad Mutua

Los breakpoints de layout (los que definen `display: grid/flex` y estructura de filas/columnas) deben ser **mutuamente excluyentes**. Si dos media queries pueden activarse simultáneamente, el que se carga después sobreescribe al anterior silenciosamente.

Breakpoints actuales del proyecto:

| Escenario | Condición | Layout |
|---|---|---|
| Mobile portrait | `max-width: 600px` | Flex column (header → content → tab-bar) |
| Landscape | `max-height: 480px` | Grid 2 filas (header + sidebar/content) |
| Desktop/Tablet | `min-width: 601px` AND `min-height: 481px` | Grid 3 filas (header + tab-bar + content) |

**Antes de crear un nuevo media query de layout**, verificar que no se superponga con los existentes. Si es necesario combinar ejes (ancho + alto), usar condiciones compuestas con `and`.

```css
/* CORRECTO — mutuamente excluyentes */
@media (max-height: 480px) { /* landscape */ }
@media (min-width: 601px) and (min-height: 481px) { /* desktop */ }

/* INCORRECTO — se superponen en landscape con ancho >600px */
@media (max-height: 480px) { /* landscape */ }
@media (min-width: 601px) { /* desktop — sobreescribe landscape */ }
```

**Excepcion**: reglas que NO definen layout (como ocultar elementos o cambiar estilos visuales) pueden usar media queries simples sin exclusividad.

## Grid con `fr`: Calcular Anchos Minimos

Antes de definir breakpoints para un grid con unidades `fr`, calcular el ancho real que obtiene cada columna en el **limite inferior** del rango:

```
ancho_columna = (viewport - scrollbar - padding_contenedor - padding_grid - gaps - borders) / total_fr
```

- Los `input[type="date"]` del navegador tienen un ancho minimo intrinseco de ~140-150px.
- Los `input[type="text"]` con padding estandar necesitan al menos ~100px.
- Los `CustomSelect` del proyecto necesitan al menos ~120px.

El breakpoint debe activarse **antes** de que cualquier columna caiga por debajo del minimo de sus hijos. Agregar `min-width: 0` a los hijos directos del grid como red de seguridad.

## Nuevas Pestanas y Componentes de Tab

Todo componente que se renderice dentro de `.tab-content` debe seguir esta estructura:

```css
.mi-tab {
  height: 100%;        /* Llenar el contenedor */
  display: flex;
  flex-direction: column;
  overflow: hidden;     /* Evitar desbordamiento */
}

.mi-tab-scrollable {
  flex: 1;             /* Ocupar espacio restante */
  min-height: 0;       /* Permitir contraccion en flex */
  overflow-y: auto;
}

.mi-tab-fixed-bottom {
  flex-shrink: 0;      /* No comprimir barras de input/acciones */
}
```

**Verificacion obligatoria** al crear un nuevo tab: probar en los 4 escenarios de layout (mobile portrait, landscape ~418-480px alto, tablet, desktop) para confirmar que `.tab-content` ocupa todo el espacio disponible sin vacios.

## Landscape (max-height: 480px)

En landscape el espacio vertical es critico (~374px disponibles despues del header). Para cualquier componente nuevo:

- Reducir paddings internos (usar 6-8px en lugar de 12-16px).
- Reducir gaps entre elementos.
- Compactar font-sizes de elementos secundarios (labels, metas, timestamps).
- El textarea o input de envio debe usar padding minimo.
- Los empty states deben ser compactos (iconos pequenos, sin padding excesivo).
