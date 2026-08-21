import { html, useState, useEffect } from 'preact-setup';
import { ConnectionIndicator } from '/static/components/ConnectionIndicator.js';
import { Tooltip } from '/static/components/Tooltip.js';

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
  onOpenEditStream,
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
        <div class="stream-name-row">
          <span class="stream-broadcaster">${broadcasterName}</span>
          ${
            online
              ? html`
                  <span class="stream-status live">
                    <span class="live-dot">●</span> LIVE
                    ${uptime ? html`<span class="uptime">(${uptime})</span>` : ''}
                  </span>
                `
              : html`<span class="stream-status offline">offline</span>`
          }
        </div>

        <${Tooltip}
          text="Hacer clic para editar el título o categoría del stream"
          position="bottom-start"
        >
          <button
            type="button"
            class="stream-meta-btn"
            onClick=${onOpenEditStream}
            aria-label="Editar información del stream"
          >
            ${category ? html`<span class="stream-category-tag">${category}</span>` : null}
            ${
              title
                ? html`<span class="stream-title-text">${title}</span>`
                : html`<span class="stream-title-text stream-title-placeholder"
                    >Editar título / categoría</span
                  >`
            }
            <i class="fa-solid fa-pen-to-square stream-edit-icon" aria-hidden="true"></i>
          </button>
        </${Tooltip}>
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
