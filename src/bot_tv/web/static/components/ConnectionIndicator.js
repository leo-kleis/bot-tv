import { html, useState, useEffect, useRef } from 'preact-setup';

/**
 * Calcula el estado global del indicador según las conexiones activas.
 * @param {boolean} connected
 * @param {boolean} ircConnected
 * @returns {'ok'|'warn'|'error'}
 */
function getOverallStatus(connected, historyLoaded, ircConnected, exited) {
  if (exited || !connected) return 'error';
  if (!historyLoaded || !ircConnected) return 'warn';
  return 'ok';
}

/**
 * Indicador unificado de estado de conexiones.
 * El popover usa position:fixed para escapar del stacking context del header
 * (que tiene backdrop-filter, lo que crea un contexto de apilamiento propio).
 *
 * @param {Object} props
 * @param {boolean} props.connected     - WebSocket al servidor
 * @param {boolean} props.historyLoaded - Carga e historial de la sesión completada
 * @param {boolean} props.ircConnected  - IRC de Twitch
 * @param {boolean} props.exited        - Bot apagado limpiamente
 */
export function ConnectionIndicator({ connected, historyLoaded, ircConnected, exited }) {
  const [open, setOpen] = useState(false);
  const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0 });
  const dotRef = useRef(null);

  const status = getOverallStatus(connected, historyLoaded, ircConnected, exited);

  // Calcular la posición del popover relativa a la ventana (fixed positioning)
  function updatePosition() {
    if (!dotRef.current) return;
    const rect = dotRef.current.getBoundingClientRect();
    setPopoverPos({
      top: rect.bottom + 10,
      left: rect.left,
    });
  }

  function toggleOpen() {
    if (!open) updatePosition();
    setOpen(v => !v);
  }

  // Cerrar al hacer click/tap fuera
  useEffect(() => {
    if (!open) return;

    function handleOutside(e) {
      if (dotRef.current && !dotRef.current.contains(e.target)) {
        // El popover está en fixed fuera del árbol DOM del dot,
        // así que debemos verificar si el click fue en el popover
        const popover = document.getElementById('conn-popover');
        if (popover && popover.contains(e.target)) return;
        setOpen(false);
      }
    }

    document.addEventListener('pointerdown', handleOutside);
    return () => document.removeEventListener('pointerdown', handleOutside);
  }, [open]);

  // Cerrar con Escape
  useEffect(() => {
    if (!open) return;

    function handleKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }

    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open]);

  // Recalcular posición al redimensionar ventana
  useEffect(() => {
    if (!open) return;
    window.addEventListener('resize', updatePosition);
    return () => window.removeEventListener('resize', updatePosition);
  }, [open]);

  let serverLabel = 'Desconectado';
  let serverStatus = 'err';
  if (exited) {
    serverLabel = 'Apagado';
    serverStatus = 'err';
  } else if (connected) {
    if (historyLoaded) {
      serverLabel = 'Conectado';
      serverStatus = 'ok';
    } else {
      serverLabel = 'Reconectando...';
      serverStatus = 'warn';
    }
  }

  // Si el servidor está desconectado o apagado, IRC automáticamente figura desconectado (err)
  const realIrcConnected = connected && historyLoaded && ircConnected;
  let ircLabel = 'Desconectado';
  let ircStatus = 'err';
  if (realIrcConnected) {
    ircLabel = 'Conectado';
    ircStatus = 'ok';
  } else if (connected && historyLoaded && !ircConnected) {
    ircLabel = 'Reconectando...';
    ircStatus = 'err';
  }

  return html`
    <div class="conn-indicator-wrap">
      <button
        ref=${dotRef}
        class="conn-indicator-dot status-${status}"
        aria-label="Estado de conexiones — click para detalles"
        aria-expanded=${open}
        aria-haspopup="true"
        onClick=${toggleOpen}
      ></button>

      ${
        open &&
        html`
          <div
            id="conn-popover"
            class="conn-popover"
            role="dialog"
            aria-label="Estado de conexiones"
            style="top:${popoverPos.top}px;left:${popoverPos.left}px"
          >
            <div class="conn-popover-title">Conexiones</div>

            <div class="conn-popover-row">
              <span class="conn-popover-dot ${serverStatus}"></span>
              <span class="conn-popover-label">Servidor</span>
              <span class="conn-popover-status ${serverStatus}">${serverLabel}</span>
            </div>

            <div class="conn-popover-row">
              <span class="conn-popover-dot ${ircStatus}"></span>
              <span class="conn-popover-label">IRC</span>
              <span class="conn-popover-status ${ircStatus}">${ircLabel}</span>
            </div>
          </div>
        `
      }
    </div>
  `;
}
