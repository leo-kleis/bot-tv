import { html, useState, useEffect, useRef, useMemo, createPortal } from 'preact-setup';
import { apiGet } from '/static/components/api.js';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';
import { formatShortDateTime } from './chartTheme.js';

const PAGE_LIMIT = 100;

/**
 * @typedef {{
 *   id: string,
 *   user_id: string,
 *   username: string,
 *   display_name: string | null,
 *   nickname: string | null,
 *   profile_image_url: string | null,
 *   message: string,
 *   timestamp: string,
 * }} AnalyticsMessage
 */

/**
 * @param {{
 *   isOpen: boolean,
 *   onClose: () => void,
 *   streamId: string,
 *   title: string,
 *   subtitle?: string,
 *   since?: string | null,
 *   until?: string | null,
 *   userId?: string | null,
 * }} props
 */
export function AnalyticsMessagesDrawer({
  isOpen,
  onClose,
  streamId,
  title,
  subtitle = '',
  since = null,
  until = null,
  userId = null,
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState(/** @type {AnalyticsMessage[]} */ ([]));
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [filterText, setFilterText] = useState('');

  const drawerRef = useRef(/** @type {HTMLDivElement | null} */ (null));
  const triggerRef = useRef(/** @type {Element | null} */ (null));
  const restoreInertRef = useRef(/** @type {(() => void) | null} */ (null));
  const closeTimerRef = useRef(/** @type {ReturnType<typeof setTimeout> | null} */ (null));
  const fetchControllerRef = useRef(/** @type {AbortController | null} */ (null));
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const isClosingRef = useRef(false);

  function handleClose() {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setOpen(false);
    if (restoreInertRef.current) {
      restoreInertRef.current();
      restoreInertRef.current = null;
    }
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = setTimeout(() => {
      closeTimerRef.current = null;
      if (onCloseRef.current) onCloseRef.current();
    }, 300);
  }

  // Gestión de apertura, aislamiento inert, focus trap, Escape y restauración de foco
  useEffect(() => {
    if (!isOpen) return;
    isClosingRef.current = false;
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    triggerRef.current = document.activeElement;
    restoreInertRef.current = setupInertIsolation(drawerRef.current);

    const frameId = requestAnimationFrame(() => {
      setOpen(true);
      if (drawerRef.current) {
        const closeBtn = drawerRef.current.querySelector('.history-header-close');
        if (closeBtn instanceof HTMLElement) {
          closeBtn.focus();
        } else {
          const first = getFocusableElements(drawerRef.current)[0];
          if (first instanceof HTMLElement) first.focus();
        }
      }
    });

    /** @param {KeyboardEvent} e */
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        handleClose();
        return;
      }
      if (e.key === 'Tab') {
        trapFocus(drawerRef.current, e);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(frameId);
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      window.removeEventListener('keydown', handleKeyDown);
      if (restoreInertRef.current) {
        restoreInertRef.current();
        restoreInertRef.current = null;
      }
      const prevEl = triggerRef.current;
      if (prevEl instanceof HTMLElement && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, [isOpen]);

  /**
   * @param {number} offsetVal
   * @param {boolean} append
   */
  async function loadMessages(offsetVal, append) {
    if (!streamId) return;
    if (fetchControllerRef.current) {
      fetchControllerRef.current.abort();
    }
    const controller = new AbortController();
    fetchControllerRef.current = controller;

    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setMessages([]);
      setTotal(0);
      setHasMore(false);
    }
    setError(null);

    const params = new window.URLSearchParams({
      stream_id: streamId,
      limit: String(PAGE_LIMIT),
      offset: String(offsetVal),
    });
    if (since) params.set('since', since);
    if (until) params.set('until', until);
    if (userId) params.set('user_id', userId);

    const res = await apiGet(`/api/analytics/messages?${params.toString()}`, {
      signal: controller.signal,
    });

    if (controller.signal.aborted || res?.aborted) return;

    setLoading(false);
    setLoadingMore(false);

    if (res && res.ok && res.data) {
      const incoming = Array.isArray(res.data.messages) ? res.data.messages : [];
      setMessages(prev => (append ? [...prev, ...incoming] : incoming));
      setTotal(Number(res.data.total || 0));
      setHasMore(Boolean(res.data.has_more));
    } else {
      setError((res && res.error) || 'No se pudieron cargar los mensajes de la sesión.');
    }
  }

  // Carga inicial cuando se abre o cambian los parámetros del filtro
  useEffect(() => {
    if (!isOpen || !streamId) return;
    setFilterText('');
    loadMessages(0, false);

    return () => {
      if (fetchControllerRef.current) {
        fetchControllerRef.current.abort();
      }
    };
  }, [isOpen, streamId, since, until, userId]);

  const filteredMessages = useMemo(() => {
    const q = filterText.trim().toLowerCase();
    if (!q) return messages;
    return messages.filter(m => {
      const author =
        `${m.nickname || ''} ${m.display_name || ''} ${m.username || ''}`.toLowerCase();
      const body = (m.message || '').toLowerCase();
      return author.includes(q) || body.includes(q);
    });
  }, [messages, filterText]);

  if (!isOpen) return null;

  return createPortal(
    html`
      <div class="history-backdrop" onClick=${handleClose} />

      <div
        class="history-drawer analytics-messages-drawer ${open ? 'open' : ''}"
        ref=${drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="analytics-messages-drawer-title"
      >
        <div class="history-header">
          <div class="history-header-info">
            <span class="history-header-name" id="analytics-messages-drawer-title">${title}</span>
            ${subtitle ? html`<span class="analytics-drawer-subtitle">${subtitle}</span>` : null}
            <span class="history-msg-count">
              ${total} ${total === 1 ? 'mensaje' : 'mensajes'} encontrados
            </span>
          </div>
          <button
            type="button"
            class="history-header-close"
            onClick=${handleClose}
            title="Cerrar panel de mensajes"
            aria-label="Cerrar panel de mensajes"
          >
            <i class="fa-solid fa-xmark" aria-hidden="true"></i>
          </button>
        </div>

        <div class="history-search">
          <div class="history-search-input-wrap">
            <i class="fa-solid fa-magnifying-glass history-search-icon" aria-hidden="true"></i>
            <input
              type="text"
              class="history-search-input"
              placeholder="Filtrar mensajes cargados..."
              aria-label="Filtrar mensajes cargados"
              value=${filterText}
              onInput=${e => setFilterText(e.target.value)}
            />
          </div>
        </div>

        <div class="history-messages">
          ${
            error
              ? html`
                  <div class="analytics-drawer-error" role="alert">
                    <span>${error}</span>
                    <button
                      type="button"
                      class="btn btn-secondary btn-sm"
                      onClick=${() => loadMessages(0, false)}
                    >
                      Reintentar
                    </button>
                  </div>
                `
              : loading
                ? html`
                    <div class="history-empty">
                      <span
                        class="history-spinner"
                        style="width:20px;height:20px;border-width:3px;"
                      ></span>
                      <p>Cargando mensajes...</p>
                    </div>
                  `
                : filteredMessages.length === 0
                  ? html`
                      <div class="history-empty">
                        <i class="fa-solid fa-comment-slash" aria-hidden="true"></i>
                        <p>
                          ${
                            messages.length > 0
                              ? 'Ningún mensaje coincide con el filtro.'
                              : 'No hay mensajes registrados en esta selección.'
                          }
                        </p>
                      </div>
                    `
                  : html`
                      <div class="history-msg-list">
                        ${filteredMessages.map(msg => {
                          const displayAuthor = msg.nickname || msg.display_name || msg.username;
                          const showHandle =
                            msg.username &&
                            displayAuthor.toLowerCase() !== msg.username.toLowerCase();
                          return html`
                            <div class="analytics-drawer-msg" key=${msg.id}>
                              <div class="analytics-drawer-msg-head">
                                <span class="analytics-drawer-msg-author">
                                  ${displayAuthor}${showHandle ? ` (@${msg.username})` : ''}
                                </span>
                                <span class="analytics-drawer-msg-time">
                                  ${formatShortDateTime(msg.timestamp)}
                                </span>
                              </div>
                              <div class="analytics-drawer-msg-text">${msg.message}</div>
                            </div>
                          `;
                        })}
                      </div>
                    `
          }
          ${
            hasMore && !loading
              ? html`
                  <div class="history-load-more">
                    <button
                      type="button"
                      class="btn btn-secondary btn-sm"
                      disabled=${loadingMore}
                      onClick=${() => loadMessages(messages.length, true)}
                    >
                      ${
                        loadingMore
                          ? html`<span class="history-spinner"></span> Cargando más...`
                          : 'Cargar más'
                      }
                    </button>
                  </div>
                `
              : null
          }
        </div>
      </div>
    `,
    document.body
  );
}
