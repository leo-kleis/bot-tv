const FOCUSABLE_SELECTOR =
  'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Devuelve los elementos enfocables visibles dentro de un contenedor.
 * @param {HTMLElement | null | undefined} container
 * @returns {HTMLElement[]}
 */
export function getFocusableElements(container) {
  if (!container) return [];
  const elements = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
    el => el instanceof HTMLElement && !el.closest('[inert]')
  );
  const visible = elements.filter(
    el => el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0
  );
  return visible.length > 0 ? visible : elements;
}

/**
 * Mantiene el foco por teclado atrapado dentro de un diálogo o drawer.
 * @param {HTMLElement | null | undefined} container
 * @param {KeyboardEvent} e
 * @returns {void}
 */
export function trapFocus(container, e) {
  if (!container || e.key !== 'Tab') return;

  const focusables = getFocusableElements(container);
  if (focusables.length === 0) {
    e.preventDefault();
    return;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const activeEl = document.activeElement;

  if (e.shiftKey) {
    if (activeEl === first || !(activeEl instanceof Node) || !container.contains(activeEl)) {
      e.preventDefault();
      last.focus();
    }
  } else if (activeEl === last || !(activeEl instanceof Node) || !container.contains(activeEl)) {
    e.preventDefault();
    first.focus();
  }
}

/**
 * Aplica `inert` a los elementos de fondo mientras un modal o drawer está abierto.
 * @param {HTMLElement | null | undefined} modalElement
 * @returns {() => void} Función para restaurar el estado previo.
 */
export function setupInertIsolation(modalElement) {
  if (!modalElement) return () => {};

  /** @type {Element[]} */
  const inertedElements = [];
  const appRoot = document.getElementById('app-root');

  if (appRoot && !appRoot.contains(modalElement)) {
    if (!appRoot.hasAttribute('inert')) {
      appRoot.setAttribute('inert', '');
      inertedElements.push(appRoot);
    }
  } else {
    /** @type {HTMLElement | null} */
    let current = modalElement;
    while (current && current !== document.body && current !== document.documentElement) {
      const parent = current.parentElement;
      if (parent) {
        for (const child of parent.children) {
          const isBackdrop = child.classList && child.classList.contains('history-backdrop');
          if (
            child !== current &&
            !child.contains(modalElement) &&
            !isBackdrop &&
            child.id !== 'stream-category-portal'
          ) {
            if (!child.hasAttribute('inert')) {
              child.setAttribute('inert', '');
              inertedElements.push(child);
            }
          }
        }
      }
      current = parent;
    }
  }

  return () => {
    for (const el of inertedElements) {
      if (el && typeof el.removeAttribute === 'function') {
        el.removeAttribute('inert');
      }
    }
  };
}
