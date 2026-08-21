import { html, useEffect, useRef } from 'preact-setup';

export function ContextMenu({ position, items, onClose }) {
  if (!position || !items || items.length === 0) return null;

  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    }
    function handleKeyDown(e) {
      if (e.key === 'Escape') onClose();
    }

    window.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('touchstart', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('touchstart', handleClickOutside);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  // Ajustar coordenadas para no salirse de la pantalla
  const x = Math.max(8, Math.min(position.x, window.innerWidth - 220));
  const y = Math.max(8, Math.min(position.y, window.innerHeight - 200));

  return html`
    <div
      ref=${menuRef}
      class="context-menu"
      style="position: fixed; top: ${y}px; left: ${x}px; z-index: var(--z-popover);"
    >
      ${items.map(
        item => html`
          <button
            class="context-menu-item ${item.isDanger ? 'is-danger' : ''}"
            onClick=${() => {
              item.onClick();
              onClose();
            }}
          >
            ${item.icon ? html`<i class="fa-solid ${item.icon}"></i>` : null}
            <span>${item.label}</span>
          </button>
        `
      )}
    </div>
  `;
}
