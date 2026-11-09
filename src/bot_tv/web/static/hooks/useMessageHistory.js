import { useState, useEffect, useRef, useCallback } from 'preact-setup';
import { apiGet } from '/static/components/api.js';

const BATCH_SIZE = 50;

export function formatTimestamp(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = String(d.getFullYear()).slice(-2);
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year}, ${hours}:${minutes}`;
  } catch {
    return iso;
  }
}

export function formatCount(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function useMessageHistory(username, search, since, until) {
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
