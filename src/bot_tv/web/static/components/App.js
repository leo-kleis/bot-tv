import { h, useState } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { ChatTab }     from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab }    from '/static/components/agent/AgentTab.js';
import { ActionsTab }  from '/static/components/actions/ActionsTab.js';
import { SettingsTab } from '/static/components/settings/SettingsTab.js';

const html = htm.bind(h);

const TABS = [
  { id: 'chat',      icon: html`<i class="fa-solid fa-comments"></i>`, label: 'Chat' },
  { id: 'followers', icon: html`<i class="fa-solid fa-heart"></i>`, label: 'Seguidores' },
  { id: 'agent',     icon: html`<i class="fa-solid fa-robot"></i>`, label: 'Agente' },
  { id: 'actions',   icon: html`<i class="fa-solid fa-bolt"></i>`, label: 'Acciones' },
  { id: 'settings',  icon: html`<i class="fa-solid fa-gear"></i>`, label: 'Ajustes' },
];

export function App({ state, dispatch, onReconnect }) {
  const [active, setActive] = useState('chat');
  const [showIrcMobile, setShowIrcMobile] = useState(false);

  if (state.exited || !state.connected) {
    const isCleanExit = state.exited;
    return html`
      <div class="offline-screen">
        <div class="offline-card">
          <span class="offline-icon ${!isCleanExit ? 'connecting' : ''}">
            <i class="fa-solid ${isCleanExit ? 'fa-power-off' : 'fa-circle-notch fa-spin'}"></i>
          </span>
          <h2>${isCleanExit ? 'Servidor Apagado' : 'Conexión Perdida'}</h2>
          <p>${isCleanExit 
            ? 'El bot se ha cerrado de forma limpia y el servidor web ha sido detenido.' 
            : 'La conexión se ha perdido o el bot está apagado. Intentando reconectar...'}</p>
          
          <button class="reconnect-btn" onClick=${onReconnect}>
            <i class="fa-solid fa-rotate"></i> Reconectar ahora
          </button>

          <span style="font-size:11px;color:var(--text-muted);margin-top:16px;display:block">
            ${isCleanExit ? 'Esperando a que el bot se encienda de nuevo...' : 'Reconectando automáticamente o al activar la pantalla...'}
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
        ${TABS.map(t => html`
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
        `)}
      </nav>

      <main class="tab-content" role="main">
        ${active === 'chat'      && html`
          <${ChatTab}
            chatMessages=${state.chatMessages}
            ircUsers=${state.ircUsers}
            showIrcMobile=${showIrcMobile}
            onToggleIrc=${setShowIrcMobile}
          />
        `}
        ${active === 'followers' && html`<${FollowersTab} followers=${state.followers} />`}
        ${active === 'agent'     && html`<${AgentTab} conversations=${state.agentConversations} dispatch=${dispatch} />`}
        ${active === 'actions'   && html`<${ActionsTab} clips=${state.clips} dispatch=${dispatch} />`}
        ${active === 'settings'  && html`<${SettingsTab} />`}
      </main>
    </div>
  `;
}
