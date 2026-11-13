import { html, createPortal, useState, useEffect, useRef, useCallback } from 'preact-setup';

const POPOVER_MIN_MARGIN_PX = 8;
const POPOVER_FALLBACK_WIDTH_PX = 235;
const POPOVER_OFFSET_Y_PX = 8;

/**
 * Calcula el estado global del indicador según las conexiones activas.
 * @param {boolean} connected
 * @param {boolean} historyLoaded
 * @param {boolean} ircConnected
 * @param {boolean} exited
 * @returns {'ok' | 'warn' | 'error'}
 */
function getOverallStatus(connected, historyLoaded, ircConnected, exited) {
  if (exited || !connected) return 'error';
  if (!historyLoaded || !ircConnected) return 'warn';
  return 'ok';
}

/**
 * Indicador unificado de estado de conexiones.
 * El popover se monta mediante createPortal en document.body para escapar del
 * stacking context del header.
 *
 * @param {Object} props
 * @param {boolean} props.connected - WebSocket al servidor
 * @param {boolean} props.historyLoaded - Carga e historial de la sesión completada
 * @param {boolean} props.ircConnected - IRC de Twitch
 * @param {boolean} props.exited - Bot apagado limpiamente
 * @param {() => void} [props.onRequestExit] - Solicitar confirmación para apagar el bot
 */
export function ConnectionIndicator({
  connected,
  historyLoaded,
  ircConnected,
  exited,
  onRequestExit,
}) {
  const [open, setOpen] = useState(false);
  const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0 });
  /** @type {import('preact').RefObject<HTMLButtonElement | null>} */
  const dotRef = useRef(null);
  /** @type {import('preact').RefObject<HTMLDivElement | null>} */
  const popoverRef = useRef(null);

  const status = getOverallStatus(connected, historyLoaded, ircConnected, exited);

  const updatePosition = useCallback(() => {
    if (!dotRef.current) return;
    const rect = dotRef.current.getBoundingClientRect();
    const maxLeft = Math.max(POPOVER_MIN_MARGIN_PX, window.innerWidth - POPOVER_FALLBACK_WIDTH_PX);
    setPopoverPos({
      top: Math.round(rect.bottom + POPOVER_OFFSET_Y_PX),
      left: Math.round(Math.max(POPOVER_MIN_MARGIN_PX, Math.min(rect.left, maxLeft))),
    });
  }, []);

  function toggleOpen() {
    if (!open) updatePosition();
    setOpen(v => !v);
  }

  // Cerrar al hacer click/tap fuera
  useEffect(() => {
    if (!open) return;

    /** @param {PointerEvent} e */
    function handleOutside(e) {
      const target = e.target;
      if (!(target instanceof Node)) return;
      const inDot = dotRef.current?.contains(target) ?? false;
      const inPopover = popoverRef.current?.contains(target) ?? false;
      if (!inDot && !inPopover) {
        setOpen(false);
      }
    }

    document.addEventListener('pointerdown', handleOutside);
    return () => document.removeEventListener('pointerdown', handleOutside);
  }, [open]);

  // Cerrar con Escape y devolver foco al indicador
  useEffect(() => {
    if (!open) return;

    /** @param {KeyboardEvent} e */
    function handleKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        dotRef.current?.focus();
      }
    }

    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open]);

  // Recalcular posición al redimensionar ventana o hacer scroll
  useEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, updatePosition]);

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

  const popoverPortal =
    open && typeof document !== 'undefined'
      ? createPortal(
          html`
            <div
              ref=${popoverRef}
              id="conn-popover"
              class="conn-popover"
              role="dialog"
              aria-label="Estado de conexiones"
              style="top:${popoverPos.top}px;left:${popoverPos.left}px"
            >
              <div class="conn-popover-title">Conexiones</div>

              <div class="conn-popover-row">
                <span class="conn-popover-dot ${serverStatus}" aria-hidden="true"></span>
                <span class="conn-popover-label">Servidor</span>
                <span class="conn-popover-status ${serverStatus}">${serverLabel}</span>
              </div>

              <div class="conn-popover-row">
                <span class="conn-popover-dot ${ircStatus}" aria-hidden="true"></span>
                <span class="conn-popover-label">IRC</span>
                <span class="conn-popover-status ${ircStatus}">${ircLabel}</span>
              </div>

              ${
                onRequestExit
                  ? html`
                      <div class="conn-popover-divider" role="separator"></div>
                      <button
                        type="button"
                        id="btn-conn-exit-bot"
                        class="btn btn-exit conn-popover-exit-btn"
                        disabled=${Boolean(exited)}
                        onClick=${() => {
                          setOpen(false);
                          onRequestExit();
                        }}
                      >
                        <i class="fa-solid fa-power-off" aria-hidden="true"></i>
                        <span>${exited ? 'Bot apagado' : 'Apagar bot'}</span>
                      </button>
                    `
                  : null
              }
            </div>
          `,
          document.body
        )
      : null;

  return html`
    <div class="conn-indicator-wrap">
      <button
        type="button"
        ref=${dotRef}
        class="conn-indicator-dot status-${status}"
        aria-label="Estado de conexiones — click para detalles"
        aria-expanded=${open}
        aria-haspopup="dialog"
        aria-controls=${open ? 'conn-popover' : undefined}
        onClick=${toggleOpen}
      ></button>
      ${popoverPortal}
    </div>
  `;
}
