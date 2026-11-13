import { useState, useEffect, useRef, useCallback } from 'preact-setup';
import { apiGet } from '/static/components/api.js';

const BATCH_SIZE = 50;

/**
 * @typedef {Object} HistoryMessage
 * @property {string} [id]
 * @property {string} timestamp
 * @property {string} [text]
 * @property {string} [message]
 * @property {string} [username]
 * @property {string} [display_name]
 */

/**
 * Formatea una fecha ISO a formato corto DD/MM/AA, HH:MM.
 * @param {string | null | undefined} iso
 * @returns {string}
 */
export function formatTimestamp(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
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

/**
 * Formatea un conteo numérico abreviando miles con sufijo `k`.
 * @param {number} n
 * @returns {string}
 */
export function formatCount(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

/**
 * Hook para paginar y filtrar el historial de mensajes de un usuario.
 * @param {string | null | undefined} username
 * @param {string} [search]
 * @param {string} [since]
 * @param {string} [until]
 * @returns {{
 *   messages: HistoryMessage[],
 *   total: number,
 *   hasMore: boolean,
 *   loading: boolean,
 *   loadingMore: boolean,
 *   loadMore: () => Promise<void>
 * }}
 */
export function useMessageHistory(username, search, since, until) {
  /** @type {[HistoryMessage[], (updater: HistoryMessage[] | ((prev: HistoryMessage[]) => HistoryMessage[])) => void]} */
  const [messages, setMessages] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const offsetRef = useRef(0);
  const requestEpochRef = useRef(0);
  /** @type {import('preact').RefObject<AbortController | null>} */
  const loadMoreControllerRef = useRef(null);

  const buildParams = useCallback(
    /** @param {number} offset */
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
    if (!username) {
      setMessages([]);
      setTotal(0);
      setHasMore(false);
      setLoading(false);
      return;
    }

    const epoch = ++requestEpochRef.current;
    const controller = new AbortController();

    if (loadMoreControllerRef.current) {
      loadMoreControllerRef.current.abort();
      loadMoreControllerRef.current = null;
    }

    async function load() {
      setLoading(true);
      setLoadingMore(false);
      offsetRef.current = 0;

      const data = await apiGet(
        `/api/users/${encodeURIComponent(String(username))}/messages?${buildParams(0)}`,
        { signal: controller.signal }
      );
      if (epoch !== requestEpochRef.current || controller.signal.aborted || data?.aborted) {
        return;
      }

      if (data && data.ok && data.data) {
        // La API retorna mensajes ORDER BY timestamp DESC; los invertimos para
        // que el más antiguo esté arriba y el más reciente abajo (estilo chat).
        const rawMessages = Array.isArray(data.data.messages) ? data.data.messages : [];
        const sorted = [...rawMessages].reverse();
        setMessages(sorted);
        setTotal(data.data.total ?? 0);
        setHasMore(Boolean(data.data.has_more));
        offsetRef.current = rawMessages.length;
      } else {
        setMessages([]);
        setTotal(0);
        setHasMore(false);
      }
      setLoading(false);
    }

    load();
    return () => {
      requestEpochRef.current += 1;
      controller.abort();
      if (loadMoreControllerRef.current) {
        loadMoreControllerRef.current.abort();
        loadMoreControllerRef.current = null;
      }
    };
  }, [username, buildParams]);

  // Carga de lote anterior (scroll al tope)
  const loadMore = useCallback(async () => {
    if (!username || loadingMore || !hasMore) return;

    const epoch = requestEpochRef.current;
    if (loadMoreControllerRef.current) {
      loadMoreControllerRef.current.abort();
    }
    const controller = new AbortController();
    loadMoreControllerRef.current = controller;

    setLoadingMore(true);
    try {
      const data = await apiGet(
        `/api/users/${encodeURIComponent(String(username))}/messages?${buildParams(offsetRef.current)}`,
        { signal: controller.signal }
      );
      if (epoch !== requestEpochRef.current || controller.signal.aborted || data?.aborted) {
        return;
      }

      if (data && data.ok && data.data) {
        const rawMessages = Array.isArray(data.data.messages) ? data.data.messages : [];
        const sorted = [...rawMessages].reverse();
        setMessages(prev => [...sorted, ...prev]);
        setHasMore(Boolean(data.data.has_more));
        offsetRef.current += rawMessages.length;
      }
    } finally {
      if (loadMoreControllerRef.current === controller) {
        loadMoreControllerRef.current = null;
      }
      if (epoch === requestEpochRef.current) {
        setLoadingMore(false);
      }
    }
  }, [username, buildParams, loadingMore, hasMore]);

  return { messages, total, hasMore, loading, loadingMore, loadMore };
}
