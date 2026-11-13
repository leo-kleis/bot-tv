import { useEffect, useRef } from 'preact-setup';

/** @typedef {import('/static/state/types.js').AppAction} AppAction */
/** @typedef {import('/static/state/types.js').AppDispatch} AppDispatch */

const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 5000;
const RECONNECT_BACKOFF_FACTOR = 1.3;
const INITIAL_CONNECT_TIMEOUT_MS = 2500;

/**
 * Mantiene la conexión WebSocket con reconexión exponencial y agrupación por frame.
 * @param {AppDispatch} dispatch
 * @returns {void}
 */
export function useWebSocket(dispatch) {
  /** @type {import('preact').RefObject<WebSocket | null>} */
  const wsRef = useRef(null);
  const reconnectRef = useRef(INITIAL_RECONNECT_MS);
  /** @type {import('preact').RefObject<ReturnType<typeof setTimeout> | null>} */
  const timeoutIdRef = useRef(null);

  useEffect(() => {
    let destroyed = false;
    /** @type {AppAction[]} */
    let queue = [];
    /** @type {number | null} */
    let rafId = null;

    function flushQueue() {
      rafId = null;
      if (destroyed || queue.length === 0) return;
      const batch = queue;
      queue = [];
      dispatch({ type: 'WS_BATCH', events: batch });
    }

    /** @param {AppAction} item */
    function enqueue(item) {
      if (destroyed) return;
      queue.push(item);
      if (rafId === null) {
        rafId = requestAnimationFrame(flushQueue);
      }
    }

    function clearReconnectTimer() {
      if (timeoutIdRef.current !== null) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
    }

    // Timeout de seguridad para no bloquear la UI si el servidor está apagado
    /** @type {ReturnType<typeof setTimeout> | null} */
    let initTimer = setTimeout(() => {
      initTimer = null;
      if (!destroyed && (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)) {
        dispatch({ type: 'WS_DISCONNECTED' });
      }
    }, INITIAL_CONNECT_TIMEOUT_MS);

    function connect() {
      if (destroyed) return;

      clearReconnectTimer();

      // Si ya hay un socket abierto o en proceso de conexión, no crear otro
      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (destroyed) {
          ws.close();
          return;
        }
        if (initTimer !== null) {
          clearTimeout(initTimer);
          initTimer = null;
        }
        reconnectRef.current = INITIAL_RECONNECT_MS;
        dispatch({ type: 'WS_CONNECTED' });
      };

      ws.onmessage = e => {
        if (destroyed) return;
        try {
          const msg = JSON.parse(String(e.data));
          if (msg.type === 'dev_reload') {
            window.location.reload();
            return;
          }
          if (msg.type === 'history_batch' && Array.isArray(msg.data)) {
            for (const item of msg.data) {
              if (item && item.type) {
                enqueue(
                  item.type === 'history_end'
                    ? { type: 'HISTORY_END' }
                    : { type: item.type, data: item.data }
                );
              }
            }
          } else if (msg.type === 'history_end') {
            enqueue({ type: 'HISTORY_END' });
          } else if (msg.type) {
            enqueue({ type: msg.type, data: msg.data });
          }
        } catch {
          // Ignorar payloads malformados sin interrumpir el socket
        }
      };

      ws.onclose = () => {
        if (destroyed) return;
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        dispatch({ type: 'WS_DISCONNECTED' });

        clearReconnectTimer();

        // Reintento continuo rápido (máx 5s) para reconectar automáticamente en móviles
        timeoutIdRef.current = setTimeout(() => {
          timeoutIdRef.current = null;
          if (destroyed) return;
          reconnectRef.current = Math.min(
            reconnectRef.current * RECONNECT_BACKOFF_FACTOR,
            MAX_RECONNECT_MS
          );
          connect();
        }, reconnectRef.current);
      };

      ws.onerror = () => {
        // En navegadores como Firefox, onerror es seguido automáticamente por onclose.
      };
    }

    connect();

    // Reaccionar a eventos móviles de primer plano y red
    const handleWakeup = () => {
      if (destroyed) return;
      const state = wsRef.current?.readyState;
      if (state !== WebSocket.OPEN && state !== WebSocket.CONNECTING) {
        reconnectRef.current = INITIAL_RECONNECT_MS;
        connect();
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        handleWakeup();
      }
    };

    window.addEventListener('online', handleWakeup);
    window.addEventListener('pageshow', handleWakeup);
    window.addEventListener('focus', handleWakeup);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      destroyed = true;
      queue = [];
      if (initTimer !== null) {
        clearTimeout(initTimer);
        initTimer = null;
      }
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      window.removeEventListener('online', handleWakeup);
      window.removeEventListener('pageshow', handleWakeup);
      window.removeEventListener('focus', handleWakeup);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      clearReconnectTimer();
      if (wsRef.current) {
        const socket = wsRef.current;
        wsRef.current = null;
        socket.onopen = null;
        socket.onmessage = null;
        socket.onclose = null;
        socket.onerror = null;
        try {
          socket.close();
        } catch {
          // Ignorar errores al cerrar socket ya cerrado
        }
      }
    };
  }, [dispatch]);
}
