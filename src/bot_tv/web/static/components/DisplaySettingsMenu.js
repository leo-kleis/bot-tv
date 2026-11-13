import { html, memo, createPortal, useState, useEffect, useRef, useCallback } from 'preact-setup';
import { useId } from 'preact/hooks';

const MIN_FONT_SIZE = 12;
const MAX_FONT_SIZE = 22;
const FONT_SIZE_STEP = 0.5;
const DEFAULT_FONT_SIZE = 14;

const STORAGE_KEY_FONT_SIZE = 'font-size';
const STORAGE_KEY_HIDE_BOTS = 'hide-bot-messages';

const POPOVER_WIDTH_PX = 290;
const POPOVER_MARGIN_PX = 12;
const POPOVER_OFFSET_Y_PX = 8;
const ESTIMATED_POPOVER_HEIGHT_PX = 190;

/**
 * Normaliza y acota un tamaño de fuente al rango permitido con pasos de 0.5px.
 * @param {number} rawValue
 * @returns {number}
 */
function clampFontSize(rawValue) {
  if (!Number.isFinite(rawValue)) return DEFAULT_FONT_SIZE;
  const clamped = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, rawValue));
  return Math.round(clamped / FONT_SIZE_STEP) * FONT_SIZE_STEP;
}

/**
 * Lee el tamaño de fuente inicial desde localStorage.
 * @returns {number}
 */
function readStoredFontSize() {
  if (typeof localStorage === 'undefined') return DEFAULT_FONT_SIZE;
  const raw = localStorage.getItem(STORAGE_KEY_FONT_SIZE);
  if (!raw) return DEFAULT_FONT_SIZE;
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) ? clampFontSize(parsed) : DEFAULT_FONT_SIZE;
}

/**
 * Lee la preferencia de ocultar bots desde localStorage.
 * @returns {boolean}
 */
function readStoredHideBots() {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY_HIDE_BOTS) === 'true';
}

/**
 * Devuelve la etiqueta descriptiva correspondiente al tamaño de fuente.
 * @param {number} size
 * @returns {string}
 */
function getFontSizeLabel(size) {
  if (size <= 13) return 'Pequeño';
  if (size <= 15) return 'Normal';
  if (size <= 17) return 'Mediano';
  if (size <= 19) return 'Grande';
  return 'Muy Grande';
}

/**
 * Emite el evento interno de sincronización entre componentes para preferencias guardadas.
 * @param {string} key
 * @param {string} value
 */
function notifyStorageSettingChanged(key, value) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('storage-settings-changed', { detail: { key, value } }));
}

/**
 * Menú popover accesible para preferencias rápidas de visualización (tamaño de fuente y filtro de bots).
 *
 * @param {Object} props
 * @param {boolean} [props.showHideBots=false]
 * @param {string} [props.buttonId]
 * @param {string} [props.label='Visualización']
 * @param {boolean} [props.compact=false]
 */
export const DisplaySettingsMenu = memo(function DisplaySettingsMenu({
  showHideBots = false,
  buttonId,
  label = 'Visualización',
  compact = false,
}) {
  const [open, setOpen] = useState(false);
  const [fontSize, setFontSize] = useState(readStoredFontSize);
  const [hideBots, setHideBots] = useState(readStoredHideBots);
  const [popoverPos, setPopoverPos] = useState({ top: 0, left: 0 });

  /** @type {import('preact').RefObject<HTMLButtonElement | null>} */
  const triggerRef = useRef(null);
  /** @type {import('preact').RefObject<HTMLDivElement | null>} */
  const popoverRef = useRef(null);

  const generatedId = useId();
  const baseId = String(generatedId).replace(/[^a-zA-Z0-9_-]/g, '_');
  const popoverId = `display-menu-popover-${baseId}`;
  const rangeId = `display-menu-range-${baseId}`;
  const hideBotsId = `display-menu-hide-bots-${baseId}`;

  // Sincronizar con cambios en otras pestañas o instancias del menú
  useEffect(() => {
    if (typeof window === 'undefined') return;

    function syncFromStorage() {
      const nextFont = readStoredFontSize();
      setFontSize(nextFont);
      document.documentElement.style.setProperty('--font-size', `${nextFont}px`);
      if (showHideBots) {
        setHideBots(readStoredHideBots());
      }
    }

    window.addEventListener('storage-settings-changed', syncFromStorage);
    window.addEventListener('storage', syncFromStorage);
    return () => {
      window.removeEventListener('storage-settings-changed', syncFromStorage);
      window.removeEventListener('storage', syncFromStorage);
    };
  }, [showHideBots]);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || typeof window === 'undefined') return;
    const rect = triggerRef.current.getBoundingClientRect();
    const effectiveWidth = Math.min(
      popoverRef.current?.offsetWidth || POPOVER_WIDTH_PX,
      window.innerWidth - POPOVER_MARGIN_PX * 2
    );
    const effectiveHeight = popoverRef.current?.offsetHeight || ESTIMATED_POPOVER_HEIGHT_PX;

    const maxLeft = Math.max(
      POPOVER_MARGIN_PX,
      window.innerWidth - effectiveWidth - POPOVER_MARGIN_PX
    );
    const preferredLeft = rect.right - effectiveWidth;
    const left = Math.round(Math.max(POPOVER_MARGIN_PX, Math.min(preferredLeft, maxLeft)));

    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < effectiveHeight + POPOVER_OFFSET_Y_PX && rect.top > spaceBelow;
    const preferredTop = openUp
      ? rect.top - effectiveHeight - POPOVER_OFFSET_Y_PX
      : rect.bottom + POPOVER_OFFSET_Y_PX;
    const maxTop = Math.max(
      POPOVER_MARGIN_PX,
      window.innerHeight - effectiveHeight - POPOVER_MARGIN_PX
    );
    const top = Math.round(Math.max(POPOVER_MARGIN_PX, Math.min(preferredTop, maxTop)));

    setPopoverPos({ top, left });
  }, []);

  // Recalcular posición cuando se abre y tras montar el popover real
  useEffect(() => {
    if (!open) return;
    updatePosition();
    const rafId = window.requestAnimationFrame(updatePosition);
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.cancelAnimationFrame(rafId);
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, updatePosition]);

  // Cerrar al hacer clic/tap fuera del disparador y del popover
  useEffect(() => {
    if (!open) return;

    /** @param {PointerEvent} e */
    function handleOutside(e) {
      const target = e.target;
      if (!(target instanceof Node)) return;
      const inTrigger = triggerRef.current?.contains(target) ?? false;
      const inPopover = popoverRef.current?.contains(target) ?? false;
      if (!inTrigger && !inPopover) {
        setOpen(false);
      }
    }

    document.addEventListener('pointerdown', handleOutside);
    return () => document.removeEventListener('pointerdown', handleOutside);
  }, [open]);

  // Cerrar con Escape y restaurar foco al botón disparador
  useEffect(() => {
    if (!open) return;

    /** @param {KeyboardEvent} e */
    function handleKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open]);

  /** @param {number} nextRaw */
  const applyFontSize = useCallback(nextRaw => {
    const nextSize = clampFontSize(nextRaw);
    const valueStr = String(nextSize);
    setFontSize(nextSize);
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--font-size', `${nextSize}px`);
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY_FONT_SIZE, valueStr);
    }
    notifyStorageSettingChanged(STORAGE_KEY_FONT_SIZE, valueStr);
  }, []);

  /** @param {Event} e */
  const handleRangeInput = useCallback(
    e => {
      if (e.currentTarget instanceof HTMLInputElement) {
        applyFontSize(Number.parseFloat(e.currentTarget.value));
      }
    },
    [applyFontSize]
  );

  /** @param {Event} e */
  const handleToggleHideBots = useCallback(e => {
    if (!(e.currentTarget instanceof HTMLInputElement)) return;
    const checked = e.currentTarget.checked;
    const valueStr = String(checked);
    setHideBots(checked);
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY_HIDE_BOTS, valueStr);
    }
    notifyStorageSettingChanged(STORAGE_KEY_HIDE_BOTS, valueStr);
  }, []);

  function handleTogglePopover() {
    if (!open) updatePosition();
    setOpen(prev => !prev);
  }

  const portalPopover =
    open && typeof document !== 'undefined'
      ? createPortal(
          html`
            <div
              ref=${popoverRef}
              id=${popoverId}
              class="display-menu-popover"
              role="dialog"
              aria-label="Opciones de visualización"
              style="top:${popoverPos.top}px;left:${popoverPos.left}px"
            >
              <div class="display-menu-header">
                <span>Visualización</span>
                <span>${fontSize}px (${getFontSizeLabel(fontSize)})</span>
              </div>

              <div class="display-menu-row">
                <label for=${rangeId}>Tamaño de texto</label>
                <div class="display-menu-stepper">
                  <button
                    type="button"
                    class="btn"
                    aria-label="Reducir tamaño de texto"
                    disabled=${fontSize <= MIN_FONT_SIZE}
                    onClick=${() => applyFontSize(fontSize - FONT_SIZE_STEP)}
                  >
                    <i class="fa-solid fa-minus" aria-hidden="true"></i>
                  </button>
                  <input
                    id=${rangeId}
                    type="range"
                    class="display-menu-range"
                    min=${MIN_FONT_SIZE}
                    max=${MAX_FONT_SIZE}
                    step=${FONT_SIZE_STEP}
                    value=${fontSize}
                    aria-label="Tamaño de texto"
                    onInput=${handleRangeInput}
                  />
                  <button
                    type="button"
                    class="btn"
                    aria-label="Aumentar tamaño de texto"
                    disabled=${fontSize >= MAX_FONT_SIZE}
                    onClick=${() => applyFontSize(fontSize + FONT_SIZE_STEP)}
                  >
                    <i class="fa-solid fa-plus" aria-hidden="true"></i>
                  </button>
                </div>
              </div>

              ${
                showHideBots
                  ? html`
                      <div class="display-menu-row display-menu-row--inline">
                        <label for=${hideBotsId}>Ocultar mensajes de bots</label>
                        <input
                          id=${hideBotsId}
                          type="checkbox"
                          class="display-menu-toggle"
                          checked=${hideBots}
                          onChange=${handleToggleHideBots}
                        />
                      </div>
                    `
                  : null
              }
            </div>
          `,
          document.body
        )
      : null;

  return html`
    <button
      ref=${triggerRef}
      type="button"
      id=${buttonId}
      class="chat-header-btn display-menu-btn"
      aria-haspopup="dialog"
      aria-expanded=${open}
      aria-controls=${open ? popoverId : undefined}
      aria-label=${label}
      title=${label}
      onClick=${handleTogglePopover}
    >
      <i class="fa-solid fa-sliders" aria-hidden="true"></i>
      ${compact ? null : html`<span>${label}</span>`}
    </button>
    ${portalPopover}
  `;
});
