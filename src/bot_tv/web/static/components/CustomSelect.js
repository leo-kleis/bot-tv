import { html, useState, useEffect, useRef } from 'preact-setup';

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
  const [alignRight, setAlignRight] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    function handler(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (open && wrapRef.current) {
      const rect = wrapRef.current.getBoundingClientRect();

      // Espacio vertical: si quedan menos de 220px abajo y hay más espacio arriba
      const windowHeight = window.innerHeight;
      const spaceBelow = windowHeight - rect.bottom;
      const spaceAbove = rect.top;
      if (spaceBelow < 220 && spaceAbove > spaceBelow) {
        setOpenUpward(true);
      } else {
        setOpenUpward(false);
      }

      // Espacio horizontal: si el dropdown mide aprox 180px y se sale por la derecha
      const windowWidth = window.innerWidth;
      const spaceRight = windowWidth - rect.left;
      if (spaceRight < 180 && rect.right > 180) {
        setAlignRight(true);
      } else {
        setAlignRight(false);
      }
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

  return html`
    <div
      class="custom-select-wrap ${className || ''} ${disabled ? 'disabled' : ''} ${
        open ? 'open' : ''
      } ${openUpward ? 'open-up' : ''} ${alignRight ? 'align-right' : ''}"
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
      ${
        open && options.length > 0
          ? html`
              <div class="custom-select-dropdown">
                ${options.map(
                  opt => html`
                    <div
                      key=${opt.value}
                      class="custom-select-item ${opt.value === value ? 'selected' : ''}"
                      onMouseDown=${() => handleSelect(opt.value)}
                    >
                      ${opt.label}
                    </div>
                  `
                )}
              </div>
            `
          : null
      }
    </div>
  `;
}
