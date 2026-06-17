import { h, useState } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { ChatTab }     from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab }    from '/static/components/agent/AgentTab.js';
import { ActionsTab }  from '/static/components/actions/ActionsTab.js';

const html = htm.bind(h);

const TABS = [
  { id: 'chat',      icon: html`<i class="fa-solid fa-comments"></i>`, label: 'Chat' },
  { id: 'followers', icon: html`<i class="fa-solid fa-heart"></i>`, label: 'Seguidores' },
  { id: 'agent',     icon: html`<i class="fa-solid fa-robot"></i>`, label: 'Agente' },
  { id: 'actions',   icon: html`<i class="fa-solid fa-bolt"></i>`, label: 'Acciones' },
];

export function App({ state, dispatch }) {
  const [active, setActive] = useState('chat');
  const [showIrcMobile, setShowIrcMobile] = useState(false);

  if (state.exited) {
    return html`
      <div class="offline-screen">
        <div class="offline-card">
          <span class="offline-icon"><i class="fa-solid fa-power-off"></i></span>
          <h2>Servidor Apagado</h2>
          <p>El bot se ha cerrado de forma limpia y el servidor web ha sido detenido.</p>
          <span style="font-size:11px;color:var(--text-muted);margin-top:16px;display:block">Ya puedes cerrar esta ventana.</span>
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
      </main>
    </div>
  `;
}
