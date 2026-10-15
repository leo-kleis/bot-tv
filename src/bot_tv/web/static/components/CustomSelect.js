import { html, useState, useEffect, useRef, render } from 'preact-setup';
import { useId } from 'preact/hooks';

export function CustomSelect({
  id,
  value,
  onChange,
  options = [],
  disabled,
  className,
  placeholder,
}) {
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0, isUp: false });
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);
  const listboxRef = useRef(null);

  const generatedId = useId();
  const selectId = id || `custom-select-${String(generatedId).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  const listboxId = `${selectId}-listbox`;
  const getOptionId = index => `${listboxId}-opt-${index}`;

  // Cerrar al hacer clic fuera del disparador y del portal
  useEffect(() => {
    function handler(e) {
      const portalEl = document.getElementById('custom-select-portal');
      if (
        wrapRef.current &&
        !wrapRef.current.contains(e.target) &&
        (!portalEl || !portalEl.contains(e.target))
      ) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Calcular posición absoluta en viewport y dirección de apertura
  const updatePosition = () => {
    if (!wrapRef.current) return;
    const rect = wrapRef.current.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    const windowWidth = window.innerWidth;

    const spaceBelow = windowHeight - rect.bottom;
    const spaceAbove = rect.top;
    const isUp = spaceBelow < 220 && spaceAbove > spaceBelow;

    const width = rect.width;
    const left = Math.max(8, Math.min(rect.left, windowWidth - Math.min(300, width) - 8));
    const top = isUp ? rect.top - 6 : rect.bottom + 6;

    setDropdownPos({
      top,
      left,
      width,
      isUp,
    });
  };

  useEffect(() => {
    if (open) {
      updatePosition();
      const handleScrollOrResize = () => updatePosition();
      window.addEventListener('resize', handleScrollOrResize);
      window.addEventListener('scroll', handleScrollOrResize, true);
      return () => {
        window.removeEventListener('resize', handleScrollOrResize);
        window.removeEventListener('scroll', handleScrollOrResize, true);
      };
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      setHighlightedIndex(-1);
    }
  }, [open]);

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

  function handleSelect(val) {
    onChange(val);
    setOpen(false);
    triggerRef.current?.focus();
  }

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
      setHighlightedIndex(prev => {
        if (prev < 0) return 0;
        return Math.min(prev + 1, options.length - 1);
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (options.length === 0) return;
      setHighlightedIndex(prev => {
        if (prev < 0) return options.length - 1;
        return Math.max(prev - 1, 0);
      });
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

  // Renderizar dropdown en portal a document.body para ser inmune a recortes por overflow
  useEffect(() => {
    let portalRoot = document.getElementById('custom-select-portal');
    if (!open || options.length === 0) {
      if (portalRoot) {
        render(null, portalRoot);
      }
      return;
    }

    if (!portalRoot) {
      portalRoot = document.createElement('div');
      portalRoot.id = 'custom-select-portal';
      document.body.appendChild(portalRoot);
    }

    const dropdownStyle = dropdownPos.isUp
      ? `position:fixed;bottom:${window.innerHeight - dropdownPos.top}px;left:${dropdownPos.left}px;min-width:${dropdownPos.width}px;`
      : `position:fixed;top:${dropdownPos.top}px;left:${dropdownPos.left}px;min-width:${dropdownPos.width}px;`;

    const activeDescendantId =
      highlightedIndex >= 0 && highlightedIndex < options.length
        ? getOptionId(highlightedIndex)
        : undefined;

    const dropdownContent = html`
      <div
        id=${listboxId}
        role="listbox"
        tabindex="-1"
        aria-activedescendant=${activeDescendantId}
        aria-labelledby=${selectId}
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
              class="custom-select-item ${isSelected ? 'selected' : ''} ${
                isHighlighted ? 'highlighted' : ''
              }"
              style=${itemStyle}
              onClick=${() => handleSelect(opt.value)}
              onMouseEnter=${() => setHighlightedIndex(index)}
            >
              ${opt.label}
            </div>
          `;
        })}
      </div>
    `;

    render(dropdownContent, portalRoot);

    if (highlightedIndex >= 0) {
      const activeEl = document.getElementById(getOptionId(highlightedIndex));
      if (activeEl && typeof activeEl.scrollIntoView === 'function') {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    }

    return () => {
      if (portalRoot) {
        render(null, portalRoot);
      }
    };
  }, [open, dropdownPos, options, value, highlightedIndex, listboxId, selectId]);

  // Limpiar portal al desmontar componente
  useEffect(() => {
    return () => {
      const portalRoot = document.getElementById('custom-select-portal');
      if (portalRoot && open) {
        render(null, portalRoot);
      }
    };
  }, [open]);

  const activeDescendantId =
    open && highlightedIndex >= 0 && highlightedIndex < options.length
      ? getOptionId(highlightedIndex)
      : undefined;

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
        aria-haspopup="listbox"
        aria-expanded=${open}
        aria-controls=${listboxId}
        aria-activedescendant=${activeDescendantId}
        ref=${triggerRef}
      >
        <span class="custom-select-value"
          >${selectedOpt ? selectedOpt.label : placeholder || 'Seleccionar...'}</span
        >
        <span class="custom-select-arrow"><i class="fa-solid fa-chevron-down"></i></span>
      </button>
    </div>
  `;
}
