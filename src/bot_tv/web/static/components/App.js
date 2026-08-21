import { html, useState, useEffect } from 'preact-setup';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { StreamTab } from '/static/components/stream/StreamTab.js';
import { ChatTab } from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab } from '/static/components/agent/AgentTab.js';
import { SettingsTab } from '/static/components/settings/SettingsTab.js';
import { ToastOverlay } from '/static/components/ToastOverlay.js';
import { StreamEditModal } from '/static/components/stream/StreamEditModal.js';
import { ConfirmModal } from '/static/components/ConfirmModal.js';

const TABS = [
  { id: 'chat', icon: html`<i class="fa-solid fa-comments"></i>`, label: 'Chat' },
  { id: 'stream', icon: html`<i class="fa-solid fa-tv"></i>`, label: 'Stream' },
  { id: 'users', icon: html`<i class="fa-solid fa-users"></i>`, label: 'Usuarios & Seguidores' },
  { id: 'agent', icon: html`<i class="fa-solid fa-robot"></i>`, label: 'Agente' },
  { id: 'settings', icon: html`<i class="fa-solid fa-gear"></i>`, label: 'Ajustes' },
];

function isMobileOrTabletDevice() {
  if (typeof navigator === 'undefined') return false;
  if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
    if (navigator.userAgentData.mobile) return true;
  }
  const ua = navigator.userAgent || '';
  if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|Tablet/i.test(ua)) {
    return true;
  }
  if (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) {
    return true;
  }
  return false;
}

export function App({ state, dispatch }) {
  const [active, setActive] = useState('chat');
  const [showIrcMobile, setShowIrcMobile] = useState(false);
  const [editStreamModalOpen, setEditStreamModalOpen] = useState(false);
  const [confirmExitOpen, setConfirmExitOpen] = useState(false);
  const isMobileDevice = isMobileOrTabletDevice();

  useEffect(() => {
    if ((!state.stream.online || isMobileDevice) && active === 'stream') {
      setActive('chat');
    }
  }, [state.stream.online, active, isMobileDevice]);

  // Limpiar contador no leído al ingresar a la pestaña de usuarios
  useEffect(() => {
    if (active === 'users' && state.followers?.unreadCount > 0) {
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

  function handleTabSelect(tabId) {
    if (tabId !== active) {
      window.history.pushState({ tab: tabId }, '');
      setActive(tabId);
    }
  }

  function handleToggleIrc(open) {
    if (open) {
      window.history.pushState({ overlay: 'irc-mobile' }, '');
      setShowIrcMobile(true);
    } else {
      setShowIrcMobile(false);
      if (window.history.state && window.history.state.overlay === 'irc-mobile') {
        window.history.back();
      }
    }
  }

  function handleOpenEditStream() {
    window.history.pushState({ modal: 'stream-edit' }, '');
    setEditStreamModalOpen(true);
  }

  function handleCloseEditStream() {
    setEditStreamModalOpen(false);
    if (window.history.state && window.history.state.modal === 'stream-edit') {
      window.history.back();
    }
  }

  function handleCancelExit() {
    setConfirmExitOpen(false);
    window.history.pushState({ tab: active || 'chat' }, '');
  }

  const filteredIrcCount = [...state.ircUsers.values()].filter(
    u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot' && u.present !== false
  ).length;

  const availableTabs = TABS.filter(t => {
    if (t.id === 'stream' && isMobileDevice) return false;
    return true;
  });

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
        />
      </header>

      <nav class="tab-bar" role="tablist">
        ${availableTabs.map(t => {
          const isDisabled = t.id === 'stream' && !state.stream.online;
          const showBadge = t.id === 'users' && unreadCount > 0;
          return html`
            <button
              key=${t.id}
              id="tab-btn-${t.id}"
              class="tab-btn ${active === t.id ? 'active' : ''} ${isDisabled ? 'disabled' : ''}"
              role="tab"
              aria-selected=${active === t.id}
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

      <main class="tab-content" role="main">
        ${
          active === 'chat' &&
          html`
            <${ChatTab}
              chatMessages=${state.chatMessages}
              ircUsers=${state.ircUsers}
              ircConnected=${state.ircConnected}
              showIrcMobile=${showIrcMobile}
              onToggleIrc=${setShowIrcMobile}
              dispatch=${dispatch}
              streamOnline=${state.stream.online}
            />
          `
        }
        ${active === 'stream' && html` <${StreamTab} channel=${state.stream.broadcasterName} /> `}
        ${active === 'users' && html`<${FollowersTab} followers=${state.followers} />`}
        ${
          active === 'agent' &&
          html`<${AgentTab} conversations=${state.agentConversations} dispatch=${dispatch} />`
        }
        ${active === 'settings' && html`<${SettingsTab} dispatch=${dispatch} />`}
      </main>
      <${ToastOverlay} toasts=${state.toasts} dispatch=${dispatch} activeTab=${active} />

      <!-- Modal de Edición de Título y Categoría a nivel raíz -->
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

      <!-- Modal de Advertencia al salir de la PWA -->
      <${ConfirmModal}
        isOpen=${confirmExitOpen}
        title="¿Deseas salir de la aplicación?"
        message="Estás en la pantalla principal. Presiona nuevamente el botón atrás para salir."
        cancelText="Permanecer en la app"
        isDanger=${false}
        onClose=${handleCancelExit}
      />
    </div>
  `;
}
