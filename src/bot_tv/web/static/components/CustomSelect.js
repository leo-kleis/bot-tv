import { html, useState, useEffect, useRef, render } from 'preact-setup';

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
  const [openUpward, setOpenUpward] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0, isUp: false });
  const wrapRef = useRef(null);

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
    setOpenUpward(isUp);

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

  const selectedOpt = options.find(o => o.value === value);

  function toggle() {
    if (disabled) return;
    setOpen(!open);
  }

  function handleSelect(val) {
    onChange(val);
    setOpen(false);
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

    const dropdownContent = html`
      <div
        class="custom-select-dropdown ${dropdownPos.isUp ? 'open-up' : ''}"
        style=${dropdownStyle}
      >
        ${options.map(
          opt => html`
            <div
              key=${opt.value}
              class="custom-select-item ${opt.value === value ? 'selected' : ''}"
              onClick=${() => handleSelect(opt.value)}
            >
              ${opt.label}
            </div>
          `
        )}
      </div>
    `;

    render(dropdownContent, portalRoot);

    return () => {
      if (portalRoot) {
        render(null, portalRoot);
      }
    };
  }, [open, dropdownPos, options, value]);

  // Limpiar portal al desmontar componente
  useEffect(() => {
    return () => {
      const portalRoot = document.getElementById('custom-select-portal');
      if (portalRoot && open) {
        render(null, portalRoot);
      }
    };
  }, [open]);

  return html`
    <div
      class="custom-select-wrap ${className || ''} ${disabled ? 'disabled' : ''} ${
        open ? 'open' : ''
      }"
      ref=${wrapRef}
    >
      <button
        id=${id}
        type="button"
        class="custom-select-trigger"
        onClick=${toggle}
        disabled=${disabled}
      >
        <span class="custom-select-value"
          >${selectedOpt ? selectedOpt.label : placeholder || 'Seleccionar...'}</span
        >
        <span class="custom-select-arrow"><i class="fa-solid fa-chevron-down"></i></span>
      </button>
    </div>
  `;
}
