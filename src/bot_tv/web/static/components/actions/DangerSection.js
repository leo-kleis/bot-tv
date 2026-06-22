import { html, useState } from 'preact-setup';
import { apiPost } from '/static/components/api.js';

export function DangerSection({ dispatch }) {
  const [confirm, setConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  async function exit() {
    setLoading(true);
    const data = await apiPost('/api/exit', {});
    setLoading(false);
    if (data.ok) {
      dispatch({ type: 'BOT_EXITED' });
    }
  }

  return html`
    <div class="section">
      <div class="section-header" style="color:var(--danger)"><span class="section-icon"><i class="fa-solid fa-triangle-exclamation"></i></span> Zona de Peligro</div>
      <div class="section-body">
        ${!confirm
          ? html`
            <div>
              <button id="btn-exit-confirm" class="btn btn-exit" onClick=${() => setConfirm(true)}>
                <i class="fa-solid fa-power-off"></i> Apagar bot
              </button>
            </div>
          `
          : html`
            <p style="font-size:13px;color:var(--text-2)">¿Seguro? Esto cerrará el proceso del bot.</p>
            <div class="action-row">
              <button id="btn-exit-cancel" class="btn" style="flex:1" onClick=${() => setConfirm(false)}>Cancelar</button>
              <button id="btn-exit-execute" class="btn btn-exit" style="flex:1" onClick=${exit} disabled=${loading}>
                ${loading ? html`<span class="spinner" style="border-top-color:var(--danger)"></span>` : 'Confirmar'}
              </button>
            </div>
          `
        }
      </div>
    </div>
  `;
}
