import { html, useState, useEffect } from 'preact-setup';
import { StreamWidget } from '/static/components/StreamWidget.js';
import { StreamTab } from '/static/components/stream/StreamTab.js';
import { ChatTab } from '/static/components/chat/ChatTab.js';
import { FollowersTab } from '/static/components/followers/FollowersTab.js';
import { AgentTab } from '/static/components/agent/AgentTab.js';
import { SettingsTab } from '/static/components/settings/SettingsTab.js';
import { ToastOverlay } from '/static/components/ToastOverlay.js';
import { StreamEditModal } from '/static/components/stream/StreamEditModal.js';

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
  const isMobileDevice = isMobileOrTabletDevice();

  useEffect(() => {
    if ((!state.stream.online || isMobileDevice) && active === 'stream') {
      setActive('chat');
    }
  }, [state.stream.online, active, isMobileDevice]);

  const filteredIrcCount = [...state.ircUsers.values()].filter(
    u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot' && u.present !== false
  ).length;

  const availableTabs = TABS.filter(t => {
    if (t.id === 'stream' && isMobileDevice) return false;
    return true;
  });

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
          onToggleIrc=${() => setShowIrcMobile(!showIrcMobile)}
          onOpenEditStream=${() => setEditStreamModalOpen(true)}
        />
      </header>

      <nav class="tab-bar" role="tablist">
        ${availableTabs.map(t => {
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

      <!-- Modal de Edición de Título y Categoría a nivel raíz -->
      ${
        editStreamModalOpen
          ? html`
              <${StreamEditModal}
                initialTitle=${state.stream.title || ''}
                initialCategory=${state.stream.category || ''}
                onClose=${() => setEditStreamModalOpen(false)}
              />
            `
          : null
      }
    </div>
  `;
}
