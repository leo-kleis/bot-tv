import { html, useState } from 'preact-setup';
import { apiPost } from '/static/components/api.js';
import { ConfirmModal } from '/static/components/ConfirmModal.js';

export function DangerSection({ dispatch }) {
  const [confirm, setConfirm] = useState(false);

  async function exit() {
    const data = await apiPost('/api/exit', {});
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

        <${ConfirmModal}
          isOpen=${confirm}
          title="¿Apagar bot?"
          message="Esto cerrará el proceso del bot de forma inmediata."
          confirmText="Confirmar"
          cancelText="Cancelar"
          isDanger=${true}
          onConfirm=${exit}
          onClose=${() => setConfirm(false)}
        />
      </div>
    </div>
  `;
}
