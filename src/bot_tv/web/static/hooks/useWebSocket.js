import { useEffect, useRef } from 'preact-setup';

export function useWebSocket(dispatch) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(1000);
  const timeoutIdRef = useRef(null);
  const connectFnRef = useRef(null);

  useEffect(() => {
    let destroyed = false;

    // Timeout de seguridad de 2.5s para no bloquear la UI en el pantalla de carga si el servidor está apagado
    const initTimer = setTimeout(() => {
      if (!destroyed && (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)) {
        dispatch({ type: 'WS_DISCONNECTED' });
      }
    }, 2500);

    function connect() {
      if (destroyed) return;

      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }

      // Si había una conexión en progreso pegada (CONNECTING), cerrarla antes de reintentar
      if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
        try {
          wsRef.current.close();
        } catch {}
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
          } else if (msg.type === 'dev_reload') {
            window.location.reload();
          } else {
            dispatch({ type: msg.type, data: msg.data });
          }
        } catch {}
      };

      ws.onclose = () => {
        if (destroyed) return;
        dispatch({ type: 'WS_DISCONNECTED' });

        if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);

        // Reintento continuo rápido (máx 5s) para reconectar automáticamente en móviles
        timeoutIdRef.current = setTimeout(() => {
          reconnectRef.current = Math.min(reconnectRef.current * 1.3, 5000);
          connect();
        }, reconnectRef.current);
      };

      ws.onerror = () => {
        try {
          ws.close();
        } catch {}
      };
    }

    connectFnRef.current = connect;
    connect();

    // Reaccionar a eventos móviles de primer plano y red
    const handleWakeup = () => {
      if (!destroyed && (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)) {
        reconnectRef.current = 1000;
        connect();
      }
    };

    window.addEventListener('online', handleWakeup);
    window.addEventListener('pageshow', handleWakeup);
    window.addEventListener('focus', handleWakeup);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        handleWakeup();
      }
    });

    return () => {
      destroyed = true;
      clearTimeout(initTimer);
      window.removeEventListener('online', handleWakeup);
      window.removeEventListener('pageshow', handleWakeup);
      window.removeEventListener('focus', handleWakeup);
      document.removeEventListener('visibilitychange', handleWakeup);
      if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);
      wsRef.current?.close();
    };
  }, [dispatch]);
}
