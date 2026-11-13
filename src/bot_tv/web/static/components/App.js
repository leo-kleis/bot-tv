import { html, useState, useEffect, useMemo, useCallback } from 'preact-setup';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { StreamTab } from '/static/components/stream/StreamTab.js';
import { ChatTab } from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab } from '/static/components/agent/AgentTab.js';
import { ToastOverlay } from '/static/components/ToastOverlay.js';
import { StreamEditModal } from '/static/components/stream/StreamEditModal.js';
import { ConfirmModal } from '/static/components/ConfirmModal.js';
import { apiPost } from '/static/components/api.js';

/** @typedef {import('/static/state/types.js').AppDispatch} AppDispatch */
/** @typedef {import('/static/state/types.js').AppState} AppState */

const SMALL_SCREEN_QUERY = '(max-width: 600px) and (min-height: 481px), (max-height: 480px)';
const DESKTOP_QUERY = '(min-width: 1025px) and (min-height: 481px)';
const LANDSCAPE_QUERY = '(max-height: 480px)';

const TABS = [
  {
    id: 'chat',
    icon: html`<i class="fa-solid fa-comments" aria-hidden="true"></i>`,
    label: 'Chat',
  },
  { id: 'stream', icon: html`<i class="fa-solid fa-tv" aria-hidden="true"></i>`, label: 'Stream' },
  {
    id: 'analytics',
    icon: html`<i class="fa-solid fa-chart-line" aria-hidden="true"></i>`,
    label: 'Analíticas',
  },
  {
    id: 'users',
    icon: html`<i class="fa-solid fa-users" aria-hidden="true"></i>`,
    label: 'Comunidad',
  },
  {
    id: 'agent',
    icon: html`<i class="fa-solid fa-robot" aria-hidden="true"></i>`,
    label: 'Agente',
  },
];

/**
 * Componente raíz de la interfaz de administración.
 *
 * @param {Object} props
 * @param {AppState} props.state
 * @param {AppDispatch} props.dispatch
 */
export function App({ state, dispatch }) {
  const [active, setActive] = useState('chat');
  /** @type {[import('preact').ComponentType | null, (comp: (() => import('preact').ComponentType) | null) => void]} */
  const [AnalyticsComp, setAnalyticsComp] = useState(null);
  const [showIrcMobile, setShowIrcMobile] = useState(false);
  const [editStreamModalOpen, setEditStreamModalOpen] = useState(false);
  const [confirmExitOpen, setConfirmExitOpen] = useState(false);
  const [confirmExitBotOpen, setConfirmExitBotOpen] = useState(false);
  const [isSmallScreen, setIsSmallScreen] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(SMALL_SCREEN_QUERY).matches;
  });
  const [isLandscape, setIsLandscape] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(LANDSCAPE_QUERY).matches;
  });

  useEffect(() => {
    if (active === 'analytics' && !AnalyticsComp) {
      import('/static/components/analytics/AnalyticsTab.js').then(mod => {
        setAnalyticsComp(() => mod.AnalyticsTab);
      });
    }
  }, [active, AnalyticsComp]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mqSmall = window.matchMedia(SMALL_SCREEN_QUERY);
    const mqDesktop = window.matchMedia(DESKTOP_QUERY);
    const mqLandscape = window.matchMedia(LANDSCAPE_QUERY);

    /** @param {MediaQueryListEvent} e */
    const handleSmall = e => setIsSmallScreen(e.matches);
    /** @param {MediaQueryListEvent} e */
    const handleDesktop = e => {
      if (e.matches) {
        setShowIrcMobile(false);
      }
    };
    /** @param {MediaQueryListEvent} e */
    const handleLandscape = e => setIsLandscape(e.matches);

    mqSmall.addEventListener('change', handleSmall);
    mqDesktop.addEventListener('change', handleDesktop);
    mqLandscape.addEventListener('change', handleLandscape);
    return () => {
      mqSmall.removeEventListener('change', handleSmall);
      mqDesktop.removeEventListener('change', handleDesktop);
      mqLandscape.removeEventListener('change', handleLandscape);
    };
  }, []);

  useEffect(() => {
    if ((!state.stream.online || isSmallScreen) && active === 'stream') {
      setActive('chat');
    }
  }, [state.stream.online, active, isSmallScreen]);

  // Limpiar contador no leído al ingresar a la pestaña de usuarios
  useEffect(() => {
    if (active === 'users' && (state.followers?.unreadCount || 0) > 0) {
      dispatch({ type: 'CLEAR_UNREAD_FOLLOWERS' });
    }
  }, [active, state.followers?.unreadCount, dispatch]);

  // Inicializar Paso 0 (base de guardia de salida) y Paso 1 (pestaña activa)
  useEffect(() => {
    if (!window.history.state || (!window.history.state.tab && !window.history.state.exitGuard)) {
      window.history.replaceState({ exitGuard: true }, '');
      window.history.pushState({ tab: 'chat' }, '');
    }
  }, []);

  // Manejo de navegación y botón atrás de Android / PWA
  useEffect(() => {
    /** @param {PopStateEvent} e */
    function handlePopState(e) {
      // 1. Si hay un drawer con backdrop activo en el DOM, no intervenir
      if (document.querySelector('.history-backdrop')) {
        return;
      }

      // 2. Si hay modal de stream abierto, cerrarlo
      if (editStreamModalOpen) {
        setEditStreamModalOpen(false);
        return;
      }

      // 3. Si hay panel IRC móvil abierto, cerrarlo
      if (showIrcMobile) {
        setShowIrcMobile(false);
        return;
      }

      // 4. Si el retroceso llega al Paso 0 (exitGuard), desplegar advertencia de salida
      if (e.state && e.state.exitGuard) {
        setConfirmExitOpen(true);
        return;
      }

      // 5. Navegación cronológica entre pestañas
      if (e.state && e.state.tab) {
        setConfirmExitOpen(false);
        setActive(e.state.tab);
      } else {
        setConfirmExitOpen(true);
      }
    }

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [editStreamModalOpen, showIrcMobile]);

  const availableTabs = useMemo(
    () =>
      TABS.filter(t => {
        if (t.id === 'stream' && isSmallScreen) return false;
        return true;
      }),
    [isSmallScreen]
  );

  const handleTabSelect = useCallback(
    /** @param {string} tabId */
    tabId => {
      if (tabId !== active) {
        window.history.pushState({ tab: tabId }, '');
        setActive(tabId);
      }
    },
    [active]
  );

  const handleTabKeyDown = useCallback(
    /** @param {KeyboardEvent} e */
    e => {
      const isArrowNext = e.key === 'ArrowRight' || e.key === 'ArrowDown';
      const isArrowPrev = e.key === 'ArrowLeft' || e.key === 'ArrowUp';
      const isHome = e.key === 'Home';
      const isEnd = e.key === 'End';

      if (!isArrowNext && !isArrowPrev && !isHome && !isEnd) {
        return;
      }

      const enabledTabs = availableTabs.filter(t => !(t.id === 'stream' && !state.stream.online));
      if (enabledTabs.length === 0) return;

      const focusedTabId = document.activeElement?.id?.startsWith('tab-btn-')
        ? document.activeElement.id.replace('tab-btn-', '')
        : active;

      let currentIndex = enabledTabs.findIndex(t => t.id === focusedTabId);
      if (currentIndex === -1) {
        currentIndex = enabledTabs.findIndex(t => t.id === active);
      }
      if (currentIndex === -1) {
        currentIndex = 0;
      }

      let targetIndex = currentIndex;
      if (isArrowNext) {
        targetIndex = (currentIndex + 1) % enabledTabs.length;
      } else if (isArrowPrev) {
        targetIndex = (currentIndex - 1 + enabledTabs.length) % enabledTabs.length;
      } else if (isHome) {
        targetIndex = 0;
      } else if (isEnd) {
        targetIndex = enabledTabs.length - 1;
      }

      e.preventDefault();
      const targetTab = enabledTabs[targetIndex];
      if (targetTab) {
        handleTabSelect(targetTab.id);
        const targetEl = document.getElementById(`tab-btn-${targetTab.id}`);
        if (targetEl) {
          targetEl.focus();
        }
      }
    },
    [availableTabs, state.stream.online, active, handleTabSelect]
  );

  const handleToggleIrc = useCallback(
    /** @param {boolean} open */
    open => {
      if (open) {
        window.history.pushState({ overlay: 'irc-mobile' }, '');
        setShowIrcMobile(true);
      } else {
        setShowIrcMobile(false);
        if (window.history.state && window.history.state.overlay === 'irc-mobile') {
          window.history.back();
        }
      }
    },
    []
  );

  const handleOpenEditStream = useCallback(() => {
    window.history.pushState({ modal: 'stream-edit' }, '');
    setEditStreamModalOpen(true);
  }, []);

  const handleCloseEditStream = useCallback(() => {
    setEditStreamModalOpen(false);
    if (window.history.state && window.history.state.modal === 'stream-edit') {
      window.history.back();
    }
  }, []);

  const handleCancelExit = useCallback(() => {
    setConfirmExitOpen(false);
    window.history.pushState({ tab: active || 'chat' }, '');
  }, [active]);

  const handleOpenConfirmExitBot = useCallback(() => {
    setConfirmExitBotOpen(true);
  }, []);

  const handleCloseConfirmExitBot = useCallback(() => {
    setConfirmExitBotOpen(false);
  }, []);

  const handleExecuteExitBot = useCallback(async () => {
    const res = await apiPost('/api/exit', {});
    setConfirmExitBotOpen(false);
    if (res.ok) {
      dispatch({ type: 'BOT_EXITED' });
    } else {
      dispatch({
        type: 'ADD_TOAST',
        toast: {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          type: 'api_error',
          data: { message: res.error || 'No se pudo apagar el bot.' },
        },
      });
    }
  }, [dispatch]);

  const filteredIrcCount = useMemo(
    () =>
      [...state.ircUsers.values()].filter(
        u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot' && u.present !== false
      ).length,
    [state.ircUsers]
  );

  const unreadCount = state.followers?.unreadCount || 0;

  return html`
    <div id="app-root">
      <header class="app-header">
        <${StreamWidget}
          stream=${state.stream}
          connected=${state.connected}
          historyLoaded=${state.historyLoaded}
          ircConnected=${state.ircConnected}
          exited=${state.exited}
          ircCount=${filteredIrcCount}
          showIrcMobile=${showIrcMobile}
          onToggleIrc=${() => handleToggleIrc(!showIrcMobile)}
          onOpenEditStream=${handleOpenEditStream}
          onRequestExit=${handleOpenConfirmExitBot}
        />
      </header>

      <nav
        class="tab-bar"
        role="tablist"
        aria-label="Navegación principal"
        aria-orientation=${isLandscape ? 'vertical' : 'horizontal'}
        onKeyDown=${handleTabKeyDown}
      >
        ${availableTabs.map(t => {
          const isDisabled = t.id === 'stream' && !state.stream.online;
          const showBadge = t.id === 'users' && unreadCount > 0;
          return html`
            <button
              type="button"
              key=${t.id}
              id="tab-btn-${t.id}"
              class="tab-btn ${active === t.id ? 'active' : ''} ${isDisabled ? 'disabled' : ''}"
              role="tab"
              aria-selected=${active === t.id}
              aria-controls="panel-${t.id}"
              tabindex=${active === t.id ? 0 : -1}
              disabled=${isDisabled}
              onClick=${() => {
                if (!isDisabled) {
                  handleTabSelect(t.id);
                }
              }}
              title=${isDisabled ? 'El stream está offline' : ''}
            >
              <span class="tab-icon">${t.icon}</span>
              ${
                showBadge
                  ? html`<span class="tab-badge">${unreadCount > 99 ? '99+' : unreadCount}</span>`
                  : null
              }
              <span class="tab-label">${t.label}</span>
            </button>
          `;
        })}
      </nav>

      <main
        class="tab-content"
        role="tabpanel"
        id="panel-${active}"
        aria-labelledby="tab-btn-${active}"
        tabindex="0"
      >
        ${
          active === 'chat' &&
          html`
            <${ChatTab}
              chatMessages=${state.chatMessages}
              ircUsers=${state.ircUsers}
              ircConnected=${state.ircConnected}
              showIrcMobile=${showIrcMobile}
              onToggleIrc=${handleToggleIrc}
              dispatch=${dispatch}
              streamOnline=${state.stream.online}
            />
          `
        }
        ${active === 'stream' && html` <${StreamTab} channel=${state.stream.broadcasterName} /> `}
        ${active === 'analytics' && (AnalyticsComp ? html`<${AnalyticsComp} />` : null)}
        ${
          active === 'users' &&
          html`<${FollowersTab} followers=${state.followers} dispatch=${dispatch} />`
        }
        ${
          active === 'agent' &&
          html`<${AgentTab} conversations=${state.agentConversations} dispatch=${dispatch} />`
        }
      </main>
      <${ToastOverlay} toasts=${state.toasts} dispatch=${dispatch} activeTab=${active} />

      ${
        editStreamModalOpen
          ? html`
              <${StreamEditModal}
                initialTitle=${state.stream.title || ''}
                initialCategory=${state.stream.category || ''}
                onClose=${handleCloseEditStream}
              />
            `
          : null
      }

      <${ConfirmModal}
        isOpen=${confirmExitOpen}
        title="¿Deseas salir de la aplicación?"
        message="Estás en la pantalla principal. Presiona nuevamente el botón atrás para salir."
        cancelText="Permanecer en la app"
        isDanger=${false}
        onClose=${handleCancelExit}
      />

      <${ConfirmModal}
        isOpen=${confirmExitBotOpen}
        title="¿Apagar bot?"
        message="Esto cerrará el proceso del bot de forma inmediata."
        confirmText="Confirmar"
        cancelText="Cancelar"
        isDanger=${true}
        onConfirm=${handleExecuteExitBot}
        onClose=${handleCloseConfirmExitBot}
      />
    </div>
  `;
}
