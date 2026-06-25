import { useEffect, useRef } from 'preact-setup';

export function useWebSocket(dispatch, historyLoaded) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(1000);
  const timeoutIdRef = useRef(null);
  const connectFnRef = useRef(null);
  const historyLoadedRef = useRef(false);

  useEffect(() => {
    historyLoadedRef.current = historyLoaded;
  }, [historyLoaded]);

  useEffect(() => {
    let destroyed = false;

    function connect() {
      if (destroyed) return;

      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }

      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        return;
      }

      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectRef.current = 1000;
        dispatch({ type: 'WS_CONNECTED' });
      };

      ws.onmessage = e => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'history_end') {
            dispatch({ type: 'HISTORY_END' });
          } else {
            dispatch({ type: msg.type, data: msg.data });
          }
        } catch {}
      };

      ws.onclose = () => {
        if (destroyed) return;
        dispatch({ type: 'WS_DISCONNECTED' });

        if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);

        timeoutIdRef.current = setTimeout(() => {
          reconnectRef.current = Math.min(reconnectRef.current * 1.5, 30000);
          connect();
        }, reconnectRef.current);
      };

      ws.onerror = () => ws.close();
    }

    connectFnRef.current = connect;
    connect();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          reconnectRef.current = 1000;
          connect();
        }
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      destroyed = true;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);
      wsRef.current?.close();
    };
  }, [dispatch]);

  const triggerReconnect = () => {
    reconnectRef.current = 1000;
    if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
      connectFnRef.current?.();
    } else {
      wsRef.current.close();
    }
  };

  return { triggerReconnect };
}
