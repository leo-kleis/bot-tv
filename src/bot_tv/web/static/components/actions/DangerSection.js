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
      <div class="section-header" style="color:var(--danger)">
        <span class="section-icon"><i class="fa-solid fa-triangle-exclamation"></i></span> Zona de
        Peligro
      </div>
      <div class="section-body">
        <div>
          <button id="btn-exit-confirm" class="btn btn-exit" onClick=${() => setConfirm(true)}>
            <i class="fa-solid fa-power-off"></i> Apagar bot
          </button>
        </div>

        ${
          confirm &&
          html`
            <div class="modal-backdrop" onClick=${() => !loading && setConfirm(false)}>
              <div
                class="modal-card"
                onClick=${e => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
                aria-describedby="modal-desc"
              >
                <span class="modal-icon">
                  <i class="fa-solid fa-triangle-exclamation"></i>
                </span>
                <h3 id="modal-title">¿Apagar bot?</h3>
                <p id="modal-desc">Esto cerrará el proceso del bot de forma inmediata.</p>
                <div class="modal-actions">
                  <button
                    id="btn-exit-cancel"
                    class="btn"
                    onClick=${() => setConfirm(false)}
                    disabled=${loading}
                  >
                    Cancelar
                  </button>
                  <button
                    id="btn-exit-execute"
                    class="btn btn-danger"
                    onClick=${exit}
                    disabled=${loading}
                  >
                    ${
                      loading
                        ? html`<span class="spinner" style="border-top-color:var(--danger)"></span>`
                        : 'Confirmar'
                    }
                  </button>
                </div>
              </div>
            </div>
          `
        }
      </div>
    </div>
  `;
}
