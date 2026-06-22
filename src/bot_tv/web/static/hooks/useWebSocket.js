import { useEffect, useRef } from '/static/lib/preact-setup.js';

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

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'history_end') {
            dispatch({ type: 'HISTORY_END' });
          } else {
            dispatch({ type: msg.type, data: msg.data });

            const alertTypes = [
              'twitch_raid',
              'twitch_subscribe',
              'twitch_sub_gift',
              'twitch_sub_message',
              'twitch_cheer',
              'twitch_points_redeem',
              'prediction_begin',
              'prediction_lock',
              'prediction_end',
              'twitch_ban',
              'twitch_unban',
              'twitch_chat_clear',
              'twitch_chat_clear_user',
              'twitch_message_delete'
            ];

            if (alertTypes.includes(msg.type) && historyLoadedRef.current) {
              const toastId = Date.now() + Math.random().toString(36).substr(2, 9);
              dispatch({
                type: 'ADD_TOAST',
                toast: { id: toastId, type: msg.type, data: msg.data }
              });
              setTimeout(() => {
                dispatch({ type: 'REMOVE_TOAST', id: toastId });
              }, 5000);
            }
          }
        } catch (_) {}
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
