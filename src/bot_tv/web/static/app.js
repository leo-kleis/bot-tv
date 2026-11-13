import './css/main.css';
import { html, render, useReducer } from 'preact-setup';
import { App } from '/static/components/App.js';
import { useWebSocket } from '/static/hooks/useWebSocket.js';
import { makeInitialState } from '/static/state/constants.js';
import { reducer } from '/static/state/reducer.js';

try {
  const savedFontSize = localStorage.getItem('font-size') || '14.5px';
  const num = Number.parseFloat(savedFontSize);
  if (!Number.isNaN(num) && num >= 12 && num <= 22) {
    document.documentElement.style.setProperty('--font-size', `${num}px`);
  }
} catch {
  // Ignorar errores de acceso a localStorage
}

function Root() {
  const [state, dispatch] = useReducer(reducer, null, makeInitialState);
  useWebSocket(dispatch);

  return html`<${App} state=${state} dispatch=${dispatch} />`;
}

const rootEl = document.getElementById('app');
if (rootEl) {
  render(html`<${Root} />`, rootEl);
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
