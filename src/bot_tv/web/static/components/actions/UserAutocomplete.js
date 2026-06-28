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

function UserBadges({ user }) {
  const badges = [
    user.is_broadcaster && html`<span class="user-badge broadcaster">Broadcaster</span>`,
    user.is_moderator && html`<span class="user-badge moderator">Moderador</span>`,
    user.is_vip && html`<span class="user-badge vip">VIP</span>`,
    user.is_subscriber && html`<span class="user-badge subscriber">Subscriptor</span>`,
    user.is_follower && html`<span class="user-badge follower">Seguidor</span>`,
    user.is_bot && html`<span class="user-badge bot">Bot</span>`,
  ].filter(Boolean);

  if (badges.length === 0) {
    return html`<span class="user-badge visitor">Visita</span>`;
  }
  return badges;
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
                        ? html`<span class="ac-nickname-inline">"${s.nickname}"</span>`
                        : ''}
                    </span>
                    <div class="ac-sub ac-badges">
                      <${UserBadges} user=${s} />
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
