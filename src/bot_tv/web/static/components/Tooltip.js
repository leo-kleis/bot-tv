import { html, useState, useRef } from 'preact-setup';

export function Tooltip({
  text,
  position = 'bottom',
  followCursor = false,
  disabled = false,
  children,
}) {
  if (!text || disabled) return children;

  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const timeoutRef = useRef(null);

  const show = e => {
    clearTimeout(timeoutRef.current);
    if (followCursor && e) {
      setCoords({ x: e.clientX, y: e.clientY });
    }
    timeoutRef.current = setTimeout(() => setVisible(true), 100);
  };

  const move = e => {
    if (followCursor && e) {
      setCoords({ x: e.clientX, y: e.clientY });
    }
  };

  const hide = () => {
    clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  const cursorStyle = followCursor
    ? `position: fixed; left: ${coords.x + 10}px; top: ${coords.y + 16}px; transform: none;`
    : '';

  return html`
    <div
      class="ui-tooltip-wrapper"
      onMouseEnter=${show}
      onMouseMove=${move}
      onMouseLeave=${hide}
      onFocus=${show}
      onBlur=${hide}
    >
      ${children}
      ${
        visible &&
        html`
          <div
            class="ui-tooltip ${followCursor ? 'ui-tooltip-cursor' : `ui-tooltip-${position}`}"
            style=${cursorStyle}
            role="tooltip"
          >
            ${text}
          </div>
        `
      }
    </div>
  `;
}
