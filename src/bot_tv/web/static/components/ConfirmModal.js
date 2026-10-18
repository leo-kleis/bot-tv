import { html, useState, useEffect, useRef } from 'preact-setup';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';

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
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const modalRef = useRef(null);
  const cardRef = useRef(null);
  const triggerRef = useRef(null);
  const loadingRef = useRef(loading);
  loadingRef.current = loading;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;

    // Guardar foco previo para restaurarlo al cerrar
    triggerRef.current = document.activeElement;

    // Aislamiento inert de elementos de fondo
    const restoreInert = setupInertIsolation(modalRef.current);

    // Mover foco inicial al primer control interactivo
    const focusTimer = requestAnimationFrame(() => {
      if (!cardRef.current) return;
      if (hasInput) {
        const inputEl = cardRef.current.querySelector('input');
        if (inputEl) {
          inputEl.focus();
          return;
        }
      }
      const cancelBtn = cardRef.current.querySelector('.modal-actions button');
      if (cancelBtn) {
        cancelBtn.focus();
      } else {
        const first = getFocusableElements(cardRef.current)[0];
        if (first) first.focus();
      }
    });

    // Control de Escape y bloqueo de tabulación dentro del diálogo
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        if (!loadingRef.current && onCloseRef.current) {
          e.preventDefault();
          e.stopPropagation();
          onCloseRef.current();
        }
        return;
      }

      if (e.key === 'Tab') {
        trapFocus(cardRef.current, e);
      }
    }

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      cancelAnimationFrame(focusTimer);
      window.removeEventListener('keydown', handleKeyDown);
      restoreInert();

      // Restaurar foco al control disparador previo
      const prevEl = triggerRef.current;
      if (prevEl && typeof prevEl.focus === 'function' && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, [isOpen, hasInput]);

  if (!isOpen) return null;

  async function handleConfirm() {
    setLoading(true);
    try {
      await onConfirm(hasInput ? inputValue : undefined);
    } finally {
      setLoading(false);
    }
  }

  return html`
    <div class="modal-backdrop" ref=${modalRef} onClick=${() => !loading && onClose && onClose()}>
      <div
        class="modal-card"
        ref=${cardRef}
        onClick=${e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby=${message ? 'confirm-modal-desc' : undefined}
      >
        <span class="modal-icon" style="color: ${isDanger ? 'var(--danger)' : 'var(--warning)'}">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </span>

        <h3 id="confirm-modal-title">${title}</h3>

        ${message ? html`<p id="confirm-modal-desc">${message}</p>` : null}
        ${
          hasInput
            ? html`
                <div style="margin-bottom: 20px; text-align: left;">
                  <input
                    type="text"
                    class="form-control"
                    style="width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); padding: 10px; font-family: var(--font); font-size: 13px;"
                    placeholder=${inputPlaceholder}
                    aria-label=${inputPlaceholder || title}
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
          ${
            onConfirm
              ? html`
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
                `
              : null
          }
        </div>
      </div>
    </div>
  `;
}
