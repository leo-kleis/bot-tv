import { html, memo, useCallback, useEffect, useRef } from 'preact-setup';
import { CustomSelect } from './CustomSelect.js';

/** @typedef {import('./CustomSelect.js').SelectOption} SelectOption */

const MAX_COMPOSER_HEIGHT_PX = 140;
/** @param {string} _val */
const NOOP_CHANGE = _val => {};

/**
 * Barra compositora multilínea unificada para el envío de mensajes (Chat y Agente).
 *
 * @param {Object} props
 * @param {string} props.value
 * @param {(value: string) => void} props.onChange
 * @param {(e: Event) => void | Promise<void>} props.onSubmit
 * @param {string} [props.placeholder]
 * @param {string} props.ariaLabel
 * @param {string} [props.submitAriaLabel]
 * @param {boolean} [props.disabled=false]
 * @param {boolean} [props.sending=false]
 * @param {boolean} [props.sendDisabled=false]
 * @param {boolean} [props.multiline=true]
 * @param {import('preact').RefObject<HTMLTextAreaElement | null>} [props.inputRef]
 * @param {string} [props.inputId]
 * @param {string} [props.submitId]
 * @param {number} [props.maxLength]
 * @param {string} [props.selectId]
 * @param {SelectOption[]} [props.selectOptions]
 * @param {string} [props.selectValue]
 * @param {(value: string) => void} [props.onSelectChange]
 * @param {string} [props.selectAriaLabel]
 * @param {boolean} [props.selectDisabled=false]
 * @param {string} [props.selectPlaceholder]
 * @param {import('preact').ComponentChildren} [props.selectTriggerPrefix]
 * @param {import('preact').ComponentChildren} [props.metaContent]
 * @param {(e: KeyboardEvent) => void} [props.onInputKeyDown]
 * @param {string} [props.className]
 */
export const ComposerBar = memo(function ComposerBar({
  value,
  onChange,
  onSubmit,
  placeholder,
  ariaLabel,
  submitAriaLabel = 'Enviar',
  disabled = false,
  sending = false,
  sendDisabled = false,
  multiline = true,
  inputRef,
  inputId,
  submitId,
  maxLength,
  selectId,
  selectOptions,
  selectValue,
  onSelectChange,
  selectAriaLabel,
  selectDisabled = false,
  selectPlaceholder,
  selectTriggerPrefix,
  metaContent,
  onInputKeyDown,
  className,
}) {
  /** @type {import('preact').RefObject<HTMLTextAreaElement | null>} */
  const localInputRef = useRef(null);

  /** @param {HTMLTextAreaElement | null} el */
  const setTextareaRef = useCallback(
    el => {
      localInputRef.current = el;
      if (inputRef) {
        inputRef.current = el;
      }
    },
    [inputRef]
  );

  // Ajustar altura del textarea automáticamente según el contenido sin superar el máximo CSS
  useEffect(() => {
    const el = localInputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_COMPOSER_HEIGHT_PX)}px`;
  }, [value]);

  const isSubmitDisabled = Boolean(sendDisabled || disabled || sending);

  /** @param {Event} e */
  function handleFormSubmit(e) {
    e.preventDefault();
    if (isSubmitDisabled) return;
    onSubmit(e);
  }

  /** @param {Event} e */
  function handleInput(e) {
    if (e.currentTarget instanceof HTMLTextAreaElement) {
      onChange(e.currentTarget.value);
    }
  }

  /** @param {KeyboardEvent} e */
  function handleKeyDown(e) {
    if (onInputKeyDown) {
      onInputKeyDown(e);
      if (e.defaultPrevented) return;
    }

    if (e.key === 'Enter' && !e.isComposing) {
      if (!multiline || !e.shiftKey) {
        e.preventDefault();
        if (!isSubmitDisabled) {
          onSubmit(e);
        }
      }
    }
  }

  const hasSelect = Array.isArray(selectOptions) && selectOptions.length > 0;
  const showToolbar = hasSelect || Boolean(metaContent);

  return html`
    <div class="composer-wrap ${disabled ? 'composer-disabled' : ''} ${className || ''}">
      <form class="composer-box" onSubmit=${handleFormSubmit}>
        <div class="composer-input-row">
          <textarea
            id=${inputId}
            ref=${setTextareaRef}
            class="composer-input"
            rows="1"
            placeholder=${placeholder}
            aria-label=${ariaLabel}
            value=${value}
            maxlength=${maxLength}
            disabled=${disabled}
            onInput=${handleInput}
            onKeyDown=${handleKeyDown}
          ></textarea>
          <button
            id=${submitId}
            type="submit"
            class="composer-send-btn"
            aria-label=${submitAriaLabel}
            disabled=${isSubmitDisabled}
          >
            ${
              sending
                ? html`<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>`
                : html`<i class="fa-solid fa-arrow-up" aria-hidden="true"></i>`
            }
          </button>
        </div>

        ${
          showToolbar
            ? html`
                <div class="composer-toolbar">
                  <div class="composer-toolbar-left">
                    ${
                      hasSelect
                        ? html`
                            <${CustomSelect}
                              id=${selectId}
                              className="composer-select"
                              value=${selectValue || ''}
                              onChange=${onSelectChange || NOOP_CHANGE}
                              options=${selectOptions}
                              disabled=${Boolean(selectDisabled || disabled)}
                              placeholder=${selectPlaceholder}
                              ariaLabel=${selectAriaLabel}
                              triggerPrefix=${selectTriggerPrefix}
                            />
                          `
                        : null
                    }
                  </div>
                  <div class="composer-toolbar-right">${metaContent || null}</div>
                </div>
              `
            : null
        }
      </form>
    </div>
  `;
});
