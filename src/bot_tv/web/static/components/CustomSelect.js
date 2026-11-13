import { html, createPortal, useState, useEffect, useRef, useCallback } from 'preact-setup';
import { useId } from 'preact/hooks';

const SPACE_BELOW_THRESHOLD_PX = 220;
const DROPDOWN_OFFSET_PX = 6;
const VIEWPORT_MARGIN_PX = 8;
const MAX_DROPDOWN_WIDTH_PX = 300;

/**
 * @typedef {Object} SelectOption
 * @property {string} value
 * @property {string} label
 */

/**
 * Selector personalizado accesible siguiendo el patrón WAI-ARIA Listbox con portal declarativo.
 *
 * @param {Object} props
 * @param {string} [props.id]
 * @param {string} props.value
 * @param {(value: string) => void} props.onChange
 * @param {SelectOption[]} [props.options=[]]
 * @param {boolean} [props.disabled]
 * @param {string} [props.className]
 * @param {string} [props.placeholder]
 * @param {string} [props.ariaLabel]
 * @param {string} [props.ariaLabelledBy]
 * @param {import('preact').ComponentChildren} [props.triggerPrefix]
 */
export function CustomSelect({
  id,
  value,
  onChange,
  options = [],
  disabled,
  className,
  placeholder,
  ariaLabel,
  ariaLabelledBy,
  triggerPrefix,
}) {
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0, isUp: false });
  /** @type {import('preact').RefObject<HTMLDivElement | null>} */
  const wrapRef = useRef(null);
  /** @type {import('preact').RefObject<HTMLButtonElement | null>} */
  const triggerRef = useRef(null);
  /** @type {import('preact').RefObject<HTMLDivElement | null>} */
  const listboxRef = useRef(null);

  const generatedId = useId();
  const selectId = id || `custom-select-${String(generatedId).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  const listboxId = `${selectId}-listbox`;

  /** @param {number} index */
  const getOptionId = useCallback(index => `${listboxId}-opt-${index}`, [listboxId]);

  // Calcular posición absoluta en viewport y dirección de apertura
  const updatePosition = useCallback(() => {
    if (!wrapRef.current) return;
    const rect = wrapRef.current.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    const windowWidth = window.innerWidth;

    const spaceBelow = windowHeight - rect.bottom;
    const spaceAbove = rect.top;
    const isUp = spaceBelow < SPACE_BELOW_THRESHOLD_PX && spaceAbove > spaceBelow;

    const width = rect.width;
    const clampedRight = windowWidth - Math.min(MAX_DROPDOWN_WIDTH_PX, width) - VIEWPORT_MARGIN_PX;
    const left = Math.max(VIEWPORT_MARGIN_PX, Math.min(rect.left, clampedRight));
    const top = isUp ? rect.top - DROPDOWN_OFFSET_PX : rect.bottom + DROPDOWN_OFFSET_PX;

    setDropdownPos({
      top,
      left,
      width,
      isUp,
    });
  }, []);

  // Cerrar al hacer clic/tap fuera del disparador y del portal
  useEffect(() => {
    if (!open) return;

    /** @param {PointerEvent} e */
    function handleOutside(e) {
      const target = e.target;
      if (!(target instanceof Node)) return;
      const inTrigger = wrapRef.current?.contains(target) ?? false;
      const inListbox = listboxRef.current?.contains(target) ?? false;
      if (!inTrigger && !inListbox) {
        setOpen(false);
      }
    }

    document.addEventListener('pointerdown', handleOutside);
    return () => document.removeEventListener('pointerdown', handleOutside);
  }, [open]);

  // Recalcular posición al abrir y ante scroll/resize
  useEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) {
      setHighlightedIndex(-1);
    }
  }, [open]);

  // Mantener visible la opción resaltada durante navegación con teclado
  useEffect(() => {
    if (!open || highlightedIndex < 0 || highlightedIndex >= options.length) return;
    const activeEl = document.getElementById(getOptionId(highlightedIndex));
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }, [open, highlightedIndex, options.length, getOptionId]);

  const selectedOpt = options.find(o => o.value === value);

  function openDropdown() {
    if (disabled || options.length === 0) return;
    const selectedIndex = options.findIndex(o => o.value === value);
    setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setOpen(true);
  }

  function toggle() {
    if (disabled) return;
    if (!open) {
      openDropdown();
    } else {
      setOpen(false);
    }
  }

  /** @param {string} val */
  function handleSelect(val) {
    onChange(val);
    setOpen(false);
    triggerRef.current?.focus();
  }

  /** @param {KeyboardEvent} e */
  function handleKeyDown(e) {
    if (disabled) return;

    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDropdown();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (options.length === 0) return;
      setHighlightedIndex(prev => (prev < 0 ? 0 : Math.min(prev + 1, options.length - 1)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (options.length === 0) return;
      setHighlightedIndex(prev => (prev < 0 ? options.length - 1 : Math.max(prev - 1, 0)));
    } else if (e.key === 'Home') {
      e.preventDefault();
      if (options.length === 0) return;
      setHighlightedIndex(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      if (options.length === 0) return;
      setHighlightedIndex(options.length - 1);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < options.length) {
        handleSelect(options[highlightedIndex].value);
      } else {
        setOpen(false);
        triggerRef.current?.focus();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    } else if (e.key === 'Tab') {
      setOpen(false);
    }
  }

  const activeDescendantId =
    open && highlightedIndex >= 0 && highlightedIndex < options.length
      ? getOptionId(highlightedIndex)
      : undefined;

  const dropdownStyle = dropdownPos.isUp
    ? `position:fixed;bottom:${window.innerHeight - dropdownPos.top}px;left:${dropdownPos.left}px;min-width:${dropdownPos.width}px;`
    : `position:fixed;top:${dropdownPos.top}px;left:${dropdownPos.left}px;min-width:${dropdownPos.width}px;`;

  const portalDropdown =
    open && options.length > 0 && typeof document !== 'undefined'
      ? createPortal(
          html`
            <div
              id=${listboxId}
              role="listbox"
              tabindex="-1"
              aria-activedescendant=${activeDescendantId}
              aria-labelledby=${ariaLabelledBy || selectId}
              class="custom-select-dropdown ${dropdownPos.isUp ? 'open-up' : ''}"
              style=${dropdownStyle}
              onKeyDown=${handleKeyDown}
              ref=${listboxRef}
            >
              ${options.map((opt, index) => {
                const optId = getOptionId(index);
                const isSelected = opt.value === value;
                const isHighlighted = highlightedIndex === index;
                const itemStyle =
                  isHighlighted && !isSelected
                    ? 'background: var(--accent-glow); color: var(--text); outline: var(--focus-ring); outline-offset: -2px;'
                    : isHighlighted && isSelected
                      ? 'outline: var(--focus-ring); outline-offset: -2px;'
                      : '';

                return html`
                  <div
                    key=${opt.value}
                    id=${optId}
                    role="option"
                    aria-selected=${isSelected}
                    class="custom-select-item custom-select-option ${isSelected ? 'selected' : ''} ${
                      isHighlighted ? 'highlighted focused' : ''
                    }"
                    style=${itemStyle}
                    onClick=${() => handleSelect(opt.value)}
                    onMouseEnter=${() => setHighlightedIndex(index)}
                  >
                    <span>${opt.label}</span>
                    ${
                      isSelected
                        ? html`<span class="custom-select-check" aria-hidden="true"
                            ><i class="fa-solid fa-check"></i
                          ></span>`
                        : null
                    }
                  </div>
                `;
              })}
            </div>
          `,
          document.body
        )
      : null;

  return html`
    <div
      class="custom-select-wrap ${className || ''} ${disabled ? 'disabled' : ''} ${
        open ? 'open' : ''
      }"
      ref=${wrapRef}
    >
      <button
        id=${selectId}
        type="button"
        class="custom-select-trigger"
        onClick=${toggle}
        onKeyDown=${handleKeyDown}
        disabled=${disabled}
        aria-label=${ariaLabel}
        aria-labelledby=${ariaLabelledBy}
        aria-haspopup="listbox"
        aria-expanded=${open}
        aria-controls=${open ? listboxId : undefined}
        aria-activedescendant=${activeDescendantId}
        ref=${triggerRef}
      >
        ${triggerPrefix ? html`<span class="custom-select-prefix">${triggerPrefix}</span>` : null}
        <span class="custom-select-value"
          >${selectedOpt ? selectedOpt.label : placeholder || 'Seleccionar...'}</span
        >
        <span class="custom-select-arrow" aria-hidden="true"
          ><i class="fa-solid fa-chevron-down"></i
        ></span>
      </button>
      ${portalDropdown}
    </div>
  `;
}
