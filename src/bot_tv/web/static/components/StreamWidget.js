import { html, useState, useEffect } from 'preact-setup';
import { ConnectionIndicator } from '/static/components/ConnectionIndicator.js';

function fmtViewers(n) {
  if (n == null) return '—';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

export function StreamWidget({
  stream,
  connected,
  historyLoaded,
  ircConnected,
  exited,
  ircCount = 0,
  showIrcMobile,
  onToggleIrc,
}) {
  const { online, broadcasterName, title, category, viewerCount, startedAt } = stream;
  const [uptime, setUptime] = useState('');

  useEffect(() => {
    if (!online || !startedAt) {
      setUptime('');
      return;
    }

    const start = new Date(startedAt).getTime();

    function update() {
      const diff = Date.now() - start;
      if (diff < 0) {
        setUptime('00:00:00');
        return;
      }
      const secs = Math.floor(diff / 1000) % 60;
      const mins = Math.floor(diff / (1000 * 60)) % 60;
      const hrs = Math.floor(diff / (1000 * 60 * 60));

      const pad = num => String(num).padStart(2, '0');
      setUptime(`${pad(hrs)}:${pad(mins)}:${pad(secs)}`);
    }

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [online, startedAt]);

  return html`
    <div class="stream-widget">
      <${ConnectionIndicator}
        connected=${connected}
        historyLoaded=${historyLoaded}
        ircConnected=${ircConnected}
        exited=${exited}
      />

      <div class="stream-info">
        <div class="stream-name">
          ${broadcasterName}
          ${
            online
              ? html`
                  <span
                    style="color:var(--online);font-size:10px;margin-left:6px;font-weight:800;letter-spacing:0.05em;display:inline-flex;align-items:center;gap:4px"
                  >
                    ● LIVE
                    ${
                      uptime
                        ? html`<span
                            style="color:var(--text-2);font-weight:600;font-variant-numeric:tabular-nums"
                            >(${uptime})</span
                          >`
                        : ''
                    }
                  </span>
                `
              : html`<span style="color:var(--text-muted);font-size:10px;margin-left:6px"
                  >offline</span
                >`
          }
        </div>
        ${
          title || category
            ? html`
                <div class="stream-meta">${[title, category].filter(Boolean).join(' · ')}</div>
              `
            : null
        }
      </div>

      ${
        online && viewerCount != null
          ? html`
              <div class="viewers-badge" title="Espectadores en vivo">
                <span class="eye-icon"><i class="fa-solid fa-eye"></i></span>
                <span>${fmtViewers(viewerCount)}</span>
              </div>
              <button
                class="viewers-badge clickable ${showIrcMobile ? 'active' : ''}"
                onClick=${onToggleIrc}
                title="Ver usuarios en el chat"
                aria-label="Ver usuarios en el chat"
              >
                <span class="users-icon">
                  <i class="fa-solid fa-users"></i>
                </span>
                <span>${ircCount}</span>
              </button>
            `
          : html`
              <button
                class="viewers-badge clickable ${showIrcMobile ? 'active' : ''}"
                onClick=${onToggleIrc}
                title="Ver usuarios en el chat"
                aria-label="Ver usuarios en el chat"
              >
                <span class="users-icon">
                  <i class="fa-solid fa-users"></i>
                </span>
                <span>${ircCount}</span>
              </button>
            `
      }
    </div>
  `;
}
