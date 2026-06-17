import { h } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';

const html = htm.bind(h);

function fmtViewers(n) {
  if (n == null) return '—';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

export function StreamWidget({ stream, connected }) {
  const { online, broadcasterName, title, category, viewerCount, viewerDiff } = stream;

  const diffEl = viewerDiff != null && viewerDiff !== 0 ? html`
    <span class="viewers-diff ${viewerDiff > 0 ? 'pos' : 'neg'}">
      ${viewerDiff > 0 ? '+' : ''}${viewerDiff}
    </span>
  ` : null;

  return html`
    <div class="stream-widget">
      <span class="conn-badge ${connected ? 'connected' : ''}" title=${connected ? 'WebSocket conectado' : 'Reconectando...'}></span>

      <span class="stream-status-dot ${online ? 'online' : ''}"></span>

      <div class="stream-info">
        <div class="stream-name">
          ${broadcasterName || 'bot-tv'}
          ${online ? html`<span style="color:var(--online);font-size:10px;margin-left:6px;font-weight:800;letter-spacing:0.05em">● LIVE</span>` : html`<span style="color:var(--text-muted);font-size:10px;margin-left:6px">offline</span>`}
        </div>
        ${(title || category) ? html`
          <div class="stream-meta">${[title, category].filter(Boolean).join(' · ')}</div>
        ` : null}
      </div>

      ${online && viewerCount != null ? html`
        <div class="viewers-badge">
          <span class="eye-icon"><i class="fa-solid fa-eye"></i></span>
          <span>${fmtViewers(viewerCount)}</span>
          ${diffEl}
        </div>
      ` : null}
    </div>
  `;
}
