import { html } from 'preact-setup';
import { useState, useEffect, useRef, useCallback } from '/static/vendor/preact-hooks.module.js';
import { apiGet } from '/static/components/api.js';

const BATCH_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 500;

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTimestamp(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-ES', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatCount(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// ── Hook de datos ─────────────────────────────────────────────────────────────

function useMessageHistory(username, search, since, until) {
  const [messages, setMessages] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const offsetRef = useRef(0);

  const buildParams = useCallback(
    offset => {
      const p = new URLSearchParams();
      p.set('limit', String(BATCH_SIZE));
      p.set('offset', String(offset));
      if (search) p.set('search', search);
      if (since) p.set('since', since);
      if (until) p.set('until', until);
      return p.toString();
    },
    [search, since, until]
  );

  // Carga inicial (o cuando cambian filtros)
  useEffect(() => {
    if (!username) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      offsetRef.current = 0;
      const data = await apiGet(
        `/api/users/${encodeURIComponent(username)}/messages?${buildParams(0)}`
      );
      if (cancelled) return;
      if (data && data.ok && data.data) {
        // La API retorna mensajes ORDER BY timestamp DESC; los invertimos para
        // que el más antiguo esté arriba y el más reciente abajo (estilo chat).
        const sorted = [...data.data.messages].reverse();
        setMessages(sorted);
        setTotal(data.data.total ?? 0);
        setHasMore(data.data.has_more ?? false);
        offsetRef.current = data.data.messages.length;
      } else {
        setMessages([]);
        setTotal(0);
        setHasMore(false);
      }
      setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [username, buildParams]);

  // Carga de lote anterior (scroll al tope)
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    const data = await apiGet(
      `/api/users/${encodeURIComponent(username)}/messages?${buildParams(offsetRef.current)}`
    );
    if (data && data.ok && data.data) {
      const sorted = [...data.data.messages].reverse();
      setMessages(prev => [...sorted, ...prev]);
      setHasMore(data.data.has_more ?? false);
      offsetRef.current += data.data.messages.length;
    }
    setLoadingMore(false);
  }, [username, buildParams, loadingMore, hasMore]);

  return { messages, total, hasMore, loading, loadingMore, loadMore };
}

// ── Componente principal ──────────────────────────────────────────────────────

export function UserHistoryDrawer({ user, onClose }) {
  const [open, setOpen] = useState(false);

  // Filtros
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');

  const messagesRef = useRef(null);
  const prevScrollHeightRef = useRef(0);

  // Activar animación de entrada y atajo de teclado Escape
  useEffect(() => {
    const id = requestAnimationFrame(() => setOpen(true));
    function handleKeyDown(e) {
      if (e.key === 'Escape') handleClose();
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Debounce del buscador
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  const { messages, total, hasMore, loading, loadingMore, loadMore } = useMessageHistory(
    user.username,
    search,
    since,
    until
  );

  // Al recibir la carga inicial, hacer scroll al fondo
  useEffect(() => {
    if (!loading && messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [loading]);

  // Al cargar más (prepend), restaurar posición de scroll
  useEffect(() => {
    if (!loadingMore && messagesRef.current) {
      const el = messagesRef.current;
      const delta = el.scrollHeight - prevScrollHeightRef.current;
      el.scrollTop = delta;
    }
  }, [loadingMore]);

  // Detectar llegada al tope para lazy-load
  function handleScroll() {
    const el = messagesRef.current;
    if (!el || loadingMore || !hasMore) return;
    if (el.scrollTop < 80) {
      prevScrollHeightRef.current = el.scrollHeight;
      loadMore();
    }
  }

  function handleClearFilters() {
    setSearchInput('');
    setSearch('');
    setSince('');
    setUntil('');
  }

  function handleClose() {
    setOpen(false);
    setTimeout(onClose, 300); // esperar animación de salida
  }

  const displayName = user.display_name || user.username;
  const showUsername =
    user.display_name && user.display_name.toLowerCase() !== user.username.toLowerCase();

  return html`
    <div class="history-backdrop" onClick=${handleClose} />

    <div class="history-drawer ${open ? 'open' : ''}">
      <!-- Header -->
      <div class="history-header">
        <div class="history-header-info">
          <span class="history-header-name">${displayName}</span>
          <div class="history-header-meta">
            ${
              showUsername
                ? html`<span class="history-header-username">@${user.username}</span>`
                : null
            }
            ${
              user.is_moderator
                ? html`<span class="irc-badge badge-moderator" style="font-size:9px;padding:1px 5px"
                    >Mod</span
                  >`
                : null
            }
            ${
              user.is_vip
                ? html`<span class="irc-badge badge-vip" style="font-size:9px;padding:1px 5px"
                    >VIP</span
                  >`
                : null
            }
            ${
              user.is_subscriber
                ? html`<span
                    class="irc-badge badge-subscriber"
                    style="font-size:9px;padding:1px 5px"
                    >Sub</span
                  >`
                : null
            }
            ${
              !loading
                ? html`<span class="history-msg-count">
                    <i class="fa-solid fa-message" style="font-size:9px;margin-right:3px;"></i>
                    ${formatCount(total)} mensajes
                  </span>`
                : null
            }
          </div>
        </div>
        <button
          class="history-header-close"
          onClick=${handleClose}
          title="Cerrar historial"
          aria-label="Cerrar historial"
        >
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Búsqueda y filtros -->
      <div class="history-search">
        <div class="history-search-input-wrap">
          <i class="fa-solid fa-magnifying-glass history-search-icon"></i>
          <input
            type="text"
            class="history-search-input"
            placeholder="Buscar en mensajes..."
            value=${searchInput}
            onInput=${e => setSearchInput(e.target.value)}
          />
        </div>
        <div class="history-search-dates">
          <input
            type="date"
            value=${since}
            onChange=${e => setSince(e.target.value)}
            max=${until || ''}
            title="Desde"
          />
          <span class="history-search-sep">—</span>
          <input
            type="date"
            value=${until}
            onChange=${e => setUntil(e.target.value)}
            min=${since || ''}
            title="Hasta"
          />
          ${
            searchInput || since || until
              ? html`
                  <button class="history-search-clear" onClick=${handleClearFilters}>
                    <i class="fa-solid fa-xmark"></i> Limpiar
                  </button>
                `
              : null
          }
        </div>
      </div>

      <!-- Mensajes -->
      <div class="history-messages" ref=${messagesRef} onScroll=${handleScroll}>
        <!-- Indicador de carga de lote anterior -->
        ${
          loadingMore
            ? html`
                <div class="history-load-more">
                  <span class="history-spinner"></span>
                  Cargando mensajes anteriores...
                </div>
              `
            : hasMore
              ? html`
                  <div class="history-load-more" style="color:var(--text-muted);font-size:11px;">
                    Sube para cargar más
                  </div>
                `
              : messages.length > 0
                ? html`
                    <div class="history-load-more" style="color:var(--text-muted);font-size:11px;">
                      Inicio del historial
                    </div>
                  `
                : null
        }

        <!-- Lista de mensajes -->
        ${
          loading
            ? html`
                <div class="history-empty">
                  <span
                    class="history-spinner"
                    style="width:20px;height:20px;border-width:3px;"
                  ></span>
                  <p>Cargando historial...</p>
                </div>
              `
            : messages.length === 0
              ? html`
                  <div class="history-empty">
                    <i class="fa-solid fa-comment-slash"></i>
                    <p>
                      ${
                        search || since || until
                          ? 'No hay mensajes que coincidan con los filtros.'
                          : `${displayName} aún no tiene mensajes registrados en este canal.`
                      }
                    </p>
                  </div>
                `
              : html`
                  <div class="history-msg-list">
                    ${messages.map(
                      (msg, i) => html`
                        <div key=${i} class="history-msg">
                          <span class="history-msg-time"> ${formatTimestamp(msg.timestamp)} </span>
                          <span class="history-msg-text">${msg.message}</span>
                        </div>
                      `
                    )}
                  </div>
                `
        }
      </div>
    </div>
  `;
}
