import { html, useState, useEffect } from 'preact-setup';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { ChatTab } from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab } from '/static/components/agent/AgentTab.js';
import { ActionsTab } from '/static/components/actions/ActionsTab.js';
import { SettingsTab } from '/static/components/settings/SettingsTab.js';
import { ToastOverlay } from '/static/components/ToastOverlay.js';

const TABS = [
  { id: 'chat', icon: html`<i class="fa-solid fa-comments"></i>`, label: 'Chat' },
  { id: 'followers', icon: html`<i class="fa-solid fa-heart"></i>`, label: 'Seguidores' },
  { id: 'agent', icon: html`<i class="fa-solid fa-robot"></i>`, label: 'Agente' },
  { id: 'actions', icon: html`<i class="fa-solid fa-bolt"></i>`, label: 'Acciones' },
  { id: 'settings', icon: html`<i class="fa-solid fa-gear"></i>`, label: 'Ajustes' },
];

export function App({ state, dispatch, onReconnect }) {
  const [active, setActive] = useState('chat');
  const [showIrcMobile, setShowIrcMobile] = useState(false);
  const [showOffline, setShowOffline] = useState(false);

  useEffect(() => {
    if (state.connected || state.initialLoad) {
      setShowOffline(false);
    } else {
      const timer = setTimeout(() => {
        setShowOffline(true);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [state.connected, state.initialLoad]);

  if (state.initialLoad || (!state.connected && !showOffline && !state.exited)) {
    return html`
      <div
        style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #0e0d12; color: #a5a1b8; font-family: 'Outfit', sans-serif; gap: 1.25rem;"
      >
        <div
          style="width: 36px; height: 36px; border: 3px solid rgba(130, 87, 229, 0.1); border-top: 3px solid #8257e5; border-radius: 50%; animation: spin 0.8s linear infinite;"
        ></div>
        <span style="font-size: 0.9rem; font-weight: 500; letter-spacing: 0.5px; opacity: 0.8;"
          >Iniciando conexión...</span
        >
        <style>
          @keyframes spin {
            0% {
              transform: rotate(0deg);
            }
            100% {
              transform: rotate(360deg);
            }
          }
        </style>
      </div>
    `;
  }

  if (state.exited || !state.connected) {
    const isCleanExit = state.exited;
    return html`
      <div class="offline-screen">
        <div class="offline-card">
          <span class="offline-icon ${!isCleanExit ? 'connecting' : ''}">
            <i class="fa-solid ${isCleanExit ? 'fa-power-off' : 'fa-circle-notch fa-spin'}"></i>
          </span>
          <h2>${isCleanExit ? 'Servidor Apagado' : 'Conexión Perdida'}</h2>
          <p>
            ${isCleanExit
              ? 'El bot se ha cerrado de forma limpia y el servidor web ha sido detenido.'
              : 'La conexión se ha perdido o el bot está apagado. Intentando reconectar...'}
          </p>

          <button class="reconnect-btn" onClick=${onReconnect}>
            <i class="fa-solid fa-rotate"></i> Reconectar ahora
          </button>

          <span style="font-size:11px;color:var(--text-muted);margin-top:16px;display:block">
            ${isCleanExit
              ? 'Esperando a que el bot se encienda de nuevo...'
              : 'Reconectando automáticamente o al activar la pantalla...'}
          </span>
        </div>
      </div>
    `;
  }

  const filteredIrcCount = [...state.ircUsers.values()].filter(
    u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot'
  ).length;

  return html`
    <div id="app-root">
      <header class="app-header">
        <${StreamWidget}
          stream=${state.stream}
          connected=${state.connected}
          ircCount=${filteredIrcCount}
          showIrcMobile=${showIrcMobile}
          onToggleIrc=${() => setShowIrcMobile(!showIrcMobile)}
        />
      </header>

      <nav class="tab-bar" role="tablist">
        ${TABS.map(
          t => html`
            <button
              key=${t.id}
              id="tab-btn-${t.id}"
              class="tab-btn ${active === t.id ? 'active' : ''}"
              role="tab"
              aria-selected=${active === t.id}
              onClick=${() => setActive(t.id)}
            >
              <span class="tab-icon">${t.icon}</span>
              <span class="tab-label">${t.label}</span>
            </button>
          `
        )}
      </nav>

      <main class="tab-content" role="main">
        ${active === 'chat' &&
        html`
          <${ChatTab}
            chatMessages=${state.chatMessages}
            ircUsers=${state.ircUsers}
            showIrcMobile=${showIrcMobile}
            onToggleIrc=${setShowIrcMobile}
            dispatch=${dispatch}
          />
        `}
        ${active === 'followers' && html`<${FollowersTab} followers=${state.followers} />`}
        ${active === 'agent' &&
        html`<${AgentTab} conversations=${state.agentConversations} dispatch=${dispatch} />`}
        ${active === 'actions' &&
        html`<${ActionsTab}
          clips=${state.clips}
          dispatch=${dispatch}
          streamOnline=${state.stream.online}
        />`}
        ${active === 'settings' && html`<${SettingsTab} />`}
      </main>
      <${ToastOverlay} toasts=${state.toasts} dispatch=${dispatch} />
    </div>
  `;
}
