import { html, useState } from 'preact-setup';
import { apiPost } from '/static/components/api.js';

export function ClipSection({ clips = [], streamOnline = false }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function createClip() {
    setLoading(true);
    setResult(null);
    const data = await apiPost('/api/create_clip', {});
    setLoading(false);
    if (data.ok) {
      setResult({ ok: true, msg: `Clip creado: ${data.data?.url || ''}` });
    } else {
      setResult({ ok: false, msg: data.error || 'Error al crear el clip.' });
    }
  }

  return html`
    <div class="section">
      <div class="section-header">
        <span class="section-icon"><i class="fa-solid fa-scissors"></i></span> Crear Clip
      </div>
      <div class="section-body">
        <button
          id="btn-create-clip"
          class="btn btn-primary btn-lg"
          onClick=${createClip}
          disabled=${loading || !streamOnline}
        >
          ${loading
            ? html`<span class="spinner"></span> Creando...`
            : !streamOnline
              ? html`<i class="fa-solid fa-circle-xmark"></i> Canal offline`
              : html`<i class="fa-solid fa-scissors"></i> Crear clip ahora`}
        </button>
        ${result
          ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}" style="word-break:break-all">
              ${result.msg}
            </div>`
          : null}
        ${clips && clips.length > 0
          ? html`
              <div style="margin-top: 12px;">
                <label
                  style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:6px"
                  >Clips Recientes</label
                >
                <div
                  style="display:flex;flex-direction:column;gap:6px;max-height:120px;overflow-y:auto"
                >
                  ${clips.map(
                    (c, i) => html`
                      <div
                        key=${i}
                        class="follower-item"
                        style="display:flex;justify-content:space-between;align-items:center"
                      >
                        <span style="font-size:11px;color:var(--text-muted)"
                          >${new Date(c.timestamp).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}</span
                        >
                        <a
                          href=${c.url}
                          target="_blank"
                          style="color:var(--accent-text);font-size:12px;text-decoration:none;word-break:break-all"
                          >${c.url}</a
                        >
                      </div>
                    `
                  )}
                </div>
              </div>
            `
          : null}
      </div>
    </div>
  `;
}
