const FOCUSABLE_SELECTOR =
  'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function getFocusableElements(container) {
  if (!container) return [];
  const elements = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR));
  const visible = elements.filter(
    el => el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0
  );
  return visible.length > 0 ? visible : elements;
}

export function trapFocus(container, e) {
  if (e.key !== 'Tab') return;

  const focusables = getFocusableElements(container);
  if (focusables.length === 0) {
    e.preventDefault();
    return;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];

  if (e.shiftKey) {
    if (document.activeElement === first || !container.contains(document.activeElement)) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (document.activeElement === last || !container.contains(document.activeElement)) {
      e.preventDefault();
      first.focus();
    }
  }
}

export function setupInertIsolation(modalElement) {
  if (!modalElement) return () => {};

  const inertedElements = [];
  const appRoot = document.getElementById('app-root');

  if (appRoot && !appRoot.contains(modalElement)) {
    if (!appRoot.hasAttribute('inert')) {
      appRoot.setAttribute('inert', '');
      inertedElements.push(appRoot);
    }
  } else {
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
