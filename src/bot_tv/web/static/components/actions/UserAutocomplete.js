import { h, useState, useEffect, useRef, useCallback } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { apiGet } from '/static/components/api.js';

const html = htm.bind(h);

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback((...args) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]);
}

export function UserAutocomplete({ value, onChange, placeholder, id }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);
  const wrapRef = useRef(null);

  const doSearch = useCallback(async (q) => {
    if (q.length < 2) { setSuggestions([]); setOpen(false); return; }
    const data = await apiGet(`/api/users/search?q=${encodeURIComponent(q)}`);
    if (data.ok && data.data?.length) {
      setSuggestions(data.data);
      setOpen(true);
      setHi(-1);
    } else {
      setSuggestions([]);
      setOpen(false);
    }
  }, []);

  const debouncedSearch = useDebounce(doSearch, 280);

  function onInput(e) {
    const v = e.target.value;
    onChange(v);
    debouncedSearch(v);
  }

  function select(item) {
    onChange(item.username);
    setSuggestions([]);
    setOpen(false);
  }

  function onKeyDown(e) {
    if (!open || !suggestions.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi(h => Math.min(h + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter' && hi >= 0) { e.preventDefault(); select(suggestions[hi]); }
    else if (e.key === 'Escape') { setOpen(false); }
  }

  // Cerrar al hacer click afuera
  useEffect(() => {
    function handler(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return html`
    <div class="autocomplete-wrap" ref=${wrapRef}>
      <input
        id=${id}
        type="text"
        placeholder=${placeholder || 'Buscar usuario...'}
        value=${value}
        onInput=${onInput}
        onKeyDown=${onKeyDown}
        onFocus=${() => value.length >= 2 && suggestions.length && setOpen(true)}
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false"
      />
      ${open && suggestions.length > 0 ? html`
        <div class="autocomplete-dropdown">
          ${suggestions.map((s, i) => html`
            <div
              key=${s.username}
              class="autocomplete-item ${i === hi ? 'highlighted' : ''}"
              onMouseDown=${() => select(s)}
            >
              <span class="ac-main">${s.display_name}</span>
              <span class="ac-sub">
                @${s.username}${s.nickname ? ` · "${s.nickname}"` : ''}
              </span>
            </div>
          `)}
        </div>
      ` : null}
    </div>
  `;
}
