import { html, useState, useEffect, useRef, useMemo, createPortal } from 'preact-setup';
import { apiGet } from '/static/components/api.js';
import { UserAvatar } from '/static/components/UserAvatar.js';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';
import { formatShortDateTime } from './chartTheme.js';

const FOLLOWER_TABS = ['all', 'follow', 'unfollow'];

/**
 * @typedef {{
 *   user_id: string,
 *   username: string,
 *   display_name: string | null,
 *   nickname: string | null,
 *   profile_image_url: string | null,
 *   event_kind: 'follow' | 'unfollow',
 *   timestamp: string,
 * }} FollowerSessionEvent
 */

/**
 * @param {{
 *   isOpen: boolean,
 *   onClose: () => void,
 *   streamId: string,
 *   sessionTitle?: string,
 * }} props
 */
export function AnalyticsFollowersDrawer({ isOpen, onClose, streamId, sessionTitle = '' }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'follow' | 'unfollow'
  const [events, setEvents] = useState(/** @type {FollowerSessionEvent[]} */ ([]));
  const [newCount, setNewCount] = useState(0);
  const [lostCount, setLostCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));
  const [searchText, setSearchText] = useState('');

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

  /**
   * @param {KeyboardEvent} e
   * @param {string} currentTabId
   */
  function handleTabKeyDown(e, currentTabId) {
    let nextTabId = null;
    const currentIndex = FOLLOWER_TABS.indexOf(currentTabId);
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextTabId = FOLLOWER_TABS[(currentIndex + 1) % FOLLOWER_TABS.length];
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextTabId = FOLLOWER_TABS[(currentIndex - 1 + FOLLOWER_TABS.length) % FOLLOWER_TABS.length];
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextTabId = FOLLOWER_TABS[0];
    } else if (e.key === 'End') {
      e.preventDefault();
      nextTabId = FOLLOWER_TABS[FOLLOWER_TABS.length - 1];
    }

    if (nextTabId) {
      setActiveTab(nextTabId);
      const nextBtn = document.getElementById(`analytics-followers-tab-${nextTabId}`);
      if (nextBtn instanceof HTMLElement) nextBtn.focus();
    }
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

  async function loadFollowerEvents() {
    if (!streamId) return;
    if (fetchControllerRef.current) {
      fetchControllerRef.current.abort();
    }
    const controller = new AbortController();
    fetchControllerRef.current = controller;

    setLoading(true);
    setError(null);

    const res = await apiGet(
      `/api/analytics/followers_events?stream_id=${encodeURIComponent(streamId)}`,
      { signal: controller.signal }
    );

    if (controller.signal.aborted || res?.aborted) return;

    setLoading(false);

    if (res && res.ok && res.data) {
      const list = Array.isArray(res.data.events) ? res.data.events : [];
      setEvents(list);
      setNewCount(Number(res.data.new_count || 0));
      setLostCount(Number(res.data.lost_count || 0));
    } else {
      setEvents([]);
      setNewCount(0);
      setLostCount(0);
      setError((res && res.error) || 'No se pudieron cargar los movimientos de seguidores.');
    }
  }

  useEffect(() => {
    if (!isOpen || !streamId) return;
    setActiveTab('all');
    setSearchText('');
    loadFollowerEvents();

    return () => {
      if (fetchControllerRef.current) {
        fetchControllerRef.current.abort();
      }
    };
  }, [isOpen, streamId]);

  const filteredEvents = useMemo(() => {
    const q = searchText.trim().toLowerCase();
    return events.filter(ev => {
      if (activeTab !== 'all' && ev.event_kind !== activeTab) return false;
      if (!q) return true;
      const text =
        `${ev.nickname || ''} ${ev.display_name || ''} ${ev.username || ''}`.toLowerCase();
      return text.includes(q);
    });
  }, [events, activeTab, searchText]);

  if (!isOpen) return null;

  const net = newCount - lostCount;
  const netLabel = `${net > 0 ? '+' : ''}${net}`;

  return createPortal(
    html`
      <div class="history-backdrop" onClick=${handleClose} />

      <div
        class="history-drawer analytics-followers-drawer ${open ? 'open' : ''}"
        ref=${drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="analytics-followers-drawer-title"
      >
        <div class="history-header">
          <div class="history-header-info">
            <span class="history-header-name" id="analytics-followers-drawer-title">
              Balance de Seguidores (${netLabel})
            </span>
            <span class="analytics-drawer-subtitle">
              ${sessionTitle ? `${sessionTitle} · ` : ''}+${newCount} nuevos / -${lostCount}
              unfollows
            </span>
          </div>
          <button
            type="button"
            class="history-header-close"
            onClick=${handleClose}
            title="Cerrar detalle de seguidores"
            aria-label="Cerrar detalle de seguidores"
          >
            <i class="fa-solid fa-xmark" aria-hidden="true"></i>
          </button>
        </div>

        <div
          class="history-drawer-tabs"
          role="tablist"
          aria-label="Filtrar movimientos de seguidores"
        >
          <button
            id="analytics-followers-tab-all"
            type="button"
            role="tab"
            aria-selected=${activeTab === 'all'}
            aria-controls="analytics-followers-panel"
            tabindex=${activeTab === 'all' ? 0 : -1}
            class="history-drawer-tab-btn ${activeTab === 'all' ? 'active' : ''}"
            onClick=${() => setActiveTab('all')}
            onKeyDown=${e => handleTabKeyDown(e, 'all')}
          >
            Todos (${events.length})
          </button>
          <button
            id="analytics-followers-tab-follow"
            type="button"
            role="tab"
            aria-selected=${activeTab === 'follow'}
            aria-controls="analytics-followers-panel"
            tabindex=${activeTab === 'follow' ? 0 : -1}
            class="history-drawer-tab-btn ${activeTab === 'follow' ? 'active' : ''}"
            onClick=${() => setActiveTab('follow')}
            onKeyDown=${e => handleTabKeyDown(e, 'follow')}
          >
            Nuevos (${newCount})
          </button>
          <button
            id="analytics-followers-tab-unfollow"
            type="button"
            role="tab"
            aria-selected=${activeTab === 'unfollow'}
            aria-controls="analytics-followers-panel"
            tabindex=${activeTab === 'unfollow' ? 0 : -1}
            class="history-drawer-tab-btn ${activeTab === 'unfollow' ? 'active' : ''}"
            onClick=${() => setActiveTab('unfollow')}
            onKeyDown=${e => handleTabKeyDown(e, 'unfollow')}
          >
            Unfollows (${lostCount})
          </button>
        </div>

        <div class="history-search">
          <div class="history-search-input-wrap">
            <i class="fa-solid fa-magnifying-glass history-search-icon" aria-hidden="true"></i>
            <input
              type="text"
              class="history-search-input"
              placeholder="Buscar por nombre o usuario..."
              aria-label="Buscar por nombre o usuario"
              value=${searchText}
              onInput=${e => setSearchText(e.target.value)}
            />
          </div>
        </div>

        <div
          id="analytics-followers-panel"
          role="tabpanel"
          aria-labelledby="analytics-followers-tab-${activeTab}"
          class="history-messages"
        >
          ${
            error
              ? html`
                  <div class="analytics-drawer-error" role="alert">
                    <span>${error}</span>
                    <button
                      type="button"
                      class="btn btn-secondary btn-sm"
                      onClick=${loadFollowerEvents}
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
                      <p>Cargando seguidores de la sesión...</p>
                    </div>
                  `
                : filteredEvents.length === 0
                  ? html`
                      <div class="history-empty">
                        <i class="fa-solid fa-users-slash" aria-hidden="true"></i>
                        <p>
                          ${
                            events.length > 0
                              ? 'Ningún usuario coincide con el filtro.'
                              : 'Sin movimientos de seguidores registrados en esta sesión.'
                          }
                        </p>
                      </div>
                    `
                  : html`
                      <ul class="analytics-follower-list">
                        ${filteredEvents.map(ev => {
                          const displayName = ev.nickname || ev.display_name || ev.username;
                          const isFollow = ev.event_kind === 'follow';
                          return html`
                            <li
                              class="analytics-follower-item"
                              key="${ev.user_id}-${ev.event_kind}-${ev.timestamp}"
                            >
                              <${UserAvatar}
                                userId=${ev.user_id}
                                displayName=${displayName}
                                color="var(--surface3)"
                                size="md"
                              />
                              <div class="analytics-follower-info">
                                <span class="analytics-follower-name">${displayName}</span>
                                <span class="analytics-follower-username">@${ev.username}</span>
                              </div>
                              <div class="analytics-follower-meta">
                                <span
                                  class="analytics-follower-badge ${
                                    isFollow ? 'is-follow' : 'is-unfollow'
                                  }"
                                >
                                  ${isFollow ? 'Nuevo seguidor' : 'Unfollow'}
                                </span>
                                <span class="analytics-follower-time">
                                  ${formatShortDateTime(ev.timestamp)}
                                </span>
                              </div>
                            </li>
                          `;
                        })}
                      </ul>
                    `
          }
        </div>
      </div>
    `,
    document.body
  );
}
