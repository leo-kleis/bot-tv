import { html, useState, useEffect, useRef, useCallback } from 'preact-setup';
import { apiGet } from '/static/components/api.js';

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return useCallback(
    (...args) => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => fn(...args), delay);
    },
    [fn, delay]
  );
}

export function UserAutocomplete({ value, onChange, placeholder, id }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);
  const wrapRef = useRef(null);

  const doSearch = useCallback(async q => {
    if (q.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
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
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi(h => Math.min(h + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi(h => Math.max(h - 1, 0));
    } else if (e.key === 'Enter' && hi >= 0) {
      e.preventDefault();
      select(suggestions[hi]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
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
      ${open && suggestions.length > 0
        ? html`
            <div class="autocomplete-dropdown">
              ${suggestions.map(
                (s, i) => html`
                  <div
                    key=${s.username}
                    class="autocomplete-item ${i === hi ? 'highlighted' : ''}"
                    onMouseDown=${() => select(s)}
                  >
                    <span class="ac-main">
                      ${s.display_name}
                      ${s.nickname
                        ? html`<span
                            class="ac-nickname-inline"
                            style="color:var(--text-muted);font-size:11.5px;font-weight:400;margin-left:6px"
                            >"${s.nickname}"</span
                          >`
                        : ''}
                    </span>
                    <div class="ac-sub" style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px">
                      ${[
                        s.is_broadcaster &&
                          html`<span
                            style="background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.25);color:#c084fc;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Broadcaster</span
                          >`,
                        s.is_moderator &&
                          html`<span
                            style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);color:#34d399;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Moderador</span
                          >`,
                        s.is_vip &&
                          html`<span
                            style="background:rgba(236,72,153,0.12);border:1px solid rgba(236,72,153,0.25);color:#f472b6;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >VIP</span
                          >`,
                        s.is_subscriber &&
                          html`<span
                            style="background:rgba(6,182,212,0.12);border:1px solid rgba(6,182,212,0.25);color:#22d3ee;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Subscriptor</span
                          >`,
                        s.is_follower &&
                          html`<span
                            style="background:rgba(155,92,255,0.12);border:1px solid rgba(155,92,255,0.25);color:#cbb0ff;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Seguidor</span
                          >`,
                        s.is_bot &&
                          html`<span
                            style="background:rgba(107,114,128,0.12);border:1px solid rgba(107,114,128,0.25);color:#9ca3af;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Bot</span
                          >`,
                      ].filter(Boolean).length === 0
                        ? html`<span
                            style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:var(--text-muted);padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                            >Visita</span
                          >`
                        : [
                            s.is_broadcaster &&
                              html`<span
                                style="background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.25);color:#c084fc;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >Broadcaster</span
                              >`,
                            s.is_moderator &&
                              html`<span
                                style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);color:#34d399;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >Moderador</span
                              >`,
                            s.is_vip &&
                              html`<span
                                style="background:rgba(236,72,153,0.12);border:1px solid rgba(236,72,153,0.25);color:#f472b6;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >VIP</span
                              >`,
                            s.is_subscriber &&
                              html`<span
                                style="background:rgba(6,182,212,0.12);border:1px solid rgba(6,182,212,0.25);color:#22d3ee;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >Subscriptor</span
                              >`,
                            s.is_follower &&
                              html`<span
                                style="background:rgba(155,92,255,0.12);border:1px solid rgba(155,92,255,0.25);color:#cbb0ff;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >Seguidor</span
                              >`,
                            s.is_bot &&
                              html`<span
                                style="background:rgba(107,114,128,0.12);border:1px solid rgba(107,114,128,0.25);color:#9ca3af;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em"
                                >Bot</span
                              >`,
                          ].filter(Boolean)}
                    </div>
                  </div>
                `
              )}
            </div>
          `
        : null}
    </div>
  `;
}
