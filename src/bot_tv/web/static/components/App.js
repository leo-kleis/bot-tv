import { html, useState, useEffect } from 'preact-setup';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { StreamTab } from '/static/components/stream/StreamTab.js';
import { ChatTab } from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab } from '/static/components/agent/AgentTab.js';
import { SettingsTab } from '/static/components/settings/SettingsTab.js';
import { ToastOverlay } from '/static/components/ToastOverlay.js';

const TABS = [
  { id: 'chat', icon: html`<i class="fa-solid fa-comments"></i>`, label: 'Chat' },
  { id: 'stream', icon: html`<i class="fa-solid fa-tv"></i>`, label: 'Stream' },
  { id: 'users', icon: html`<i class="fa-solid fa-users"></i>`, label: 'Usuarios & Seguidores' },
  { id: 'agent', icon: html`<i class="fa-solid fa-robot"></i>`, label: 'Agente' },
  { id: 'settings', icon: html`<i class="fa-solid fa-gear"></i>`, label: 'Ajustes' },
];

export function App({ state, dispatch }) {
  const [active, setActive] = useState('chat');
  const [showIrcMobile, setShowIrcMobile] = useState(false);

  useEffect(() => {
    if (!state.stream.online && active === 'stream') {
      setActive('chat');
    }
  }, [state.stream.online, active]);

  const filteredIrcCount = [...state.ircUsers.values()].filter(
    u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot' && u.present !== false
  ).length;

  return html`
    <div id="app-root">
      <header class="app-header">
        <${StreamWidget}
          stream=${state.stream}
          connected=${state.connected}
          ircConnected=${state.ircConnected}
          exited=${state.exited}
          ircCount=${filteredIrcCount}
          showIrcMobile=${showIrcMobile}
          onToggleIrc=${() => setShowIrcMobile(!showIrcMobile)}
        />
      </header>

      <nav class="tab-bar" role="tablist">
        ${TABS.map(t => {
          const isDisabled = t.id === 'stream' && !state.stream.online;
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
                  setActive(t.id);
                }
              }}
              title=${isDisabled ? 'El stream está offline' : ''}
            >
              <span class="tab-icon">${t.icon}</span>
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
      <${ToastOverlay} toasts=${state.toasts} dispatch=${dispatch} />
    </div>
  `;
}
