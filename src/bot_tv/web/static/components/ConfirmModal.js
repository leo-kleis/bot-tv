import { html, useState } from 'preact-setup';

export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  isDanger = true,
  hasInput = false,
  inputPlaceholder = '',
  onConfirm,
  onClose,
}) {
  if (!isOpen) return null;

  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await onConfirm(hasInput ? inputValue : undefined);
    } finally {
      setLoading(false);
    }
  }

  return html`
    <div class="modal-backdrop" onClick=${() => !loading && onClose()}>
      <div
        class="modal-card"
        onClick=${e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <span class="modal-icon" style="color: ${isDanger ? 'var(--danger)' : 'var(--warning)'}">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </span>

        <h3 id="modal-title">${title}</h3>

        ${message ? html`<p id="modal-desc">${message}</p>` : null}
        ${
          hasInput
            ? html`
                <div style="margin-bottom: 20px; text-align: left;">
                  <input
                    type="text"
                    class="form-control"
                    style="width: 100%; background: var(--surface2); border: var(--border); border-radius: var(--radius-xs); color: var(--text); padding: 10px; font-family: var(--font); font-size: 13px; outline: none;"
                    placeholder=${inputPlaceholder}
                    value=${inputValue}
                    onInput=${e => setInputValue(e.target.value)}
                    disabled=${loading}
                  />
                </div>
              `
            : null
        }

        <div class="modal-actions">
          <button class="btn" onClick=${onClose} disabled=${loading}>${cancelText}</button>
          <button
            class="btn ${isDanger ? 'btn-danger' : 'btn-primary'}"
            onClick=${handleConfirm}
            disabled=${loading}
          >
            ${
              loading
                ? html`<span
                    class="spinner"
                    style="border-top-color:${isDanger ? 'var(--danger)' : 'var(--accent)'}"
                  ></span>`
                : confirmText
            }
          </button>
        </div>
      </div>
    </div>
  `;
}
