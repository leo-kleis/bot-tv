import { html, useState, useEffect, useCallback, useMemo, useRef } from 'preact-setup';
import { apiGet } from '/static/components/api.js';
import { AnalyticsFilterBar } from './AnalyticsFilterBar.js';
import { AnalyticsSummaryCards } from './AnalyticsSummaryCards.js';
import { ViewersTimelineChart } from './ViewersTimelineChart.js';
import { ChatActivityChart } from './ChatActivityChart.js';
import { TopChattersChart } from './TopChattersChart.js';
import { StreamEventsChart } from './StreamEventsChart.js';
import { AnalyticsSkeleton } from './AnalyticsSkeleton.js';
import { AnalyticsEmptyState } from './AnalyticsEmptyState.js';
import { AnalyticsMessagesDrawer } from './AnalyticsMessagesDrawer.js';
import { AnalyticsFollowersDrawer } from './AnalyticsFollowersDrawer.js';
import { formatShortDateTime } from './chartTheme.js';

/**
 * @typedef {{
 *   stream_id?: string | null,
 *   channel_id?: string | null,
 *   title?: string | null,
 *   category_name?: string | null,
 *   started_at?: string | null,
 *   ended_at?: string | null,
 *   duration_seconds?: number,
 *   is_live?: boolean,
 *   peak_viewers?: number,
 *   avg_viewers?: number | null,
 *   total_messages?: number,
 *   messages_per_minute?: number,
 *   total_events?: number,
 *   events_detail?: string,
 *   new_followers?: number,
 *   lost_followers?: number,
 *   net_followers?: number,
 * }} AnalyticsOverview
 */

export function AnalyticsTab() {
  const [sessions, setSessions] = useState(/** @type {Array<Record<string, unknown>>} */ ([]));
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [chatInterval, setChatInterval] = useState(5);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(/** @type {string | null} */ (null));

  // Estados de datos de analíticas
  const [overview, setOverview] = useState(/** @type {AnalyticsOverview | null} */ (null));
  const [viewersTimeline, setViewersTimeline] = useState(
    /** @type {Array<Record<string, unknown>>} */ ([])
  );
  const [chatActivity, setChatActivity] = useState(
    /** @type {Array<Record<string, unknown>>} */ ([])
  );
  const [topChatters, setTopChatters] = useState(
    /** @type {Array<Record<string, unknown>>} */ ([])
  );
  const [streamEvents, setStreamEvents] = useState(
    /** @type {Record<string, unknown> | null} */ (null)
  );
  const [followersDrawerOpen, setFollowersDrawerOpen] = useState(false);
  const [drawerState, setDrawerState] = useState(
    /**
     * @type {{
     *   isOpen: boolean,
     *   title: string,
     *   subtitle: string,
     *   since: string | null,
     *   until: string | null,
     *   userId: string | null,
     * }}
     */ ({
      isOpen: false,
      title: '',
      subtitle: '',
      since: null,
      until: null,
      userId: null,
    })
  );

  const isMountedRef = useRef(true);
  const batchControllerRef = useRef(/** @type {AbortController | null} */ (null));
  const chatIntervalControllerRef = useRef(/** @type {AbortController | null} */ (null));

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (batchControllerRef.current) {
        batchControllerRef.current.abort();
      }
      if (chatIntervalControllerRef.current) {
        chatIntervalControllerRef.current.abort();
      }
    };
  }, []);

  // Sesión actualmente seleccionada (siempre comparada por stream_id string)
  const currentSession = useMemo(() => {
    if (!sessions || sessions.length === 0) return null;
    if (!selectedSessionId) return sessions[0] || null;
    return sessions.find(s => String(s.stream_id) === String(selectedSessionId)) || sessions[0];
  }, [sessions, selectedSessionId]);

  // Carga de todas las métricas en paralelo
  const fetchAnalyticsData = useCallback(
    /**
     * @param {string} sessionId
     * @param {number} interval
     * @param {boolean} [isBackground]
     */
    async (sessionId, interval, isBackground = false) => {
      if (!isMountedRef.current) return;
      if (batchControllerRef.current) {
        batchControllerRef.current.abort();
      }
      const controller = new AbortController();
      batchControllerRef.current = controller;
      const { signal } = controller;

      if (!isBackground) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      setError(null);

      try {
        const encodedId = sessionId ? encodeURIComponent(String(sessionId)) : '';
        const streamParam = encodedId ? `?stream_id=${encodedId}` : '';
        const chatParam = encodedId
          ? `?stream_id=${encodedId}&interval_minutes=${interval}`
          : `?interval_minutes=${interval}`;
        const topChattersParam = encodedId
          ? `?stream_id=${encodedId}&limit=10`
          : `?period=24h&limit=10`;

        const [overviewRes, timelineRes, chatRes, chattersRes, eventsRes] =
          await Promise.allSettled([
            apiGet(`/api/analytics/overview${streamParam}`, { signal }),
            encodedId
              ? apiGet(`/api/analytics/viewers_timeline${streamParam}`, { signal })
              : Promise.resolve(null),
            encodedId
              ? apiGet(`/api/analytics/chat_activity${chatParam}`, { signal })
              : Promise.resolve(null),
            apiGet(`/api/analytics/top_chatters${topChattersParam}`, { signal }),
            encodedId
              ? apiGet(`/api/analytics/stream_events${streamParam}`, { signal })
              : Promise.resolve(null),
          ]);

        if (!isMountedRef.current || signal.aborted) return;

        if (
          overviewRes.status === 'fulfilled' &&
          overviewRes.value &&
          overviewRes.value.ok !== false
        ) {
          setOverview(overviewRes.value.data || overviewRes.value);
        }

        if (
          timelineRes.status === 'fulfilled' &&
          timelineRes.value &&
          timelineRes.value.ok !== false
        ) {
          const payload = timelineRes.value.data ?? timelineRes.value;
          setViewersTimeline(
            Array.isArray(payload) ? payload : payload.timeline || payload.data || []
          );
        } else if (!encodedId) {
          setViewersTimeline([]);
        }

        if (chatRes.status === 'fulfilled' && chatRes.value && chatRes.value.ok !== false) {
          const payload = chatRes.value.data ?? chatRes.value;
          setChatActivity(
            Array.isArray(payload) ? payload : payload.activity || payload.data || []
          );
        } else if (!encodedId) {
          setChatActivity([]);
        }

        if (
          chattersRes.status === 'fulfilled' &&
          chattersRes.value &&
          chattersRes.value.ok !== false
        ) {
          const payload = chattersRes.value.data ?? chattersRes.value;
          setTopChatters(Array.isArray(payload) ? payload : payload.chatters || payload.data || []);
        }

        if (eventsRes.status === 'fulfilled' && eventsRes.value && eventsRes.value.ok !== false) {
          setStreamEvents(eventsRes.value.data || eventsRes.value);
        } else if (!encodedId) {
          setStreamEvents(null);
        }
      } catch (err) {
        if (isMountedRef.current && !signal.aborted) {
          const message = err instanceof Error ? err.message : 'Error al obtener datos analíticos';
          setError(message);
        }
      } finally {
        if (isMountedRef.current && !signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    []
  );

  // Inicialización de sesiones
  useEffect(() => {
    const controller = new AbortController();

    async function initSessions() {
      try {
        const res = await apiGet('/api/analytics/stream_sessions?limit=50', {
          signal: controller.signal,
        });
        if (controller.signal.aborted || !isMountedRef.current) return;

        if (res && res.ok !== false) {
          const raw = res.data ?? res;
          const list = Array.isArray(raw) ? raw : raw.sessions || raw.data || [];
          setSessions(list);

          if (list.length > 0) {
            const live = list.find(s => Boolean(s.is_live));
            const initialItem = live || list[0];
            const initialId = initialItem?.stream_id ? String(initialItem.stream_id) : '';
            setSelectedSessionId(initialId);
            fetchAnalyticsData(initialId, chatInterval);
          } else {
            fetchAnalyticsData('', chatInterval);
          }
        } else {
          fetchAnalyticsData('', chatInterval);
        }
      } catch (err) {
        if (!controller.signal.aborted && isMountedRef.current) {
          const message = err instanceof Error ? err.message : 'Error al conectar con el servidor';
          setError(message);
          setLoading(false);
        }
      }
    }

    initSessions();

    return () => {
      controller.abort();
    };
  }, [fetchAnalyticsData]);

  // Manejo de cambio de sesión
  const handleSelectSession = useCallback(
    /** @param {string} newId */
    newId => {
      const normalized = newId ? String(newId) : '';
      setSelectedSessionId(normalized);
      setDrawerState(prev => (prev.isOpen ? { ...prev, isOpen: false } : prev));
      setFollowersDrawerOpen(false);
      fetchAnalyticsData(normalized, chatInterval);
    },
    [chatInterval, fetchAnalyticsData]
  );

  const handleSelectBucket = useCallback(
    /**
     * @param {{ since: string, until: string, label: string, count: number }} bucket
     */
    bucket => {
      if (!selectedSessionId) return;
      setDrawerState({
        isOpen: true,
        title: `Mensajes del intervalo ${bucket.label}`,
        subtitle: `${formatShortDateTime(bucket.since)} — ${formatShortDateTime(bucket.until)}`,
        since: bucket.since,
        until: bucket.until,
        userId: null,
      });
    },
    [selectedSessionId]
  );

  const handleSelectChatter = useCallback(
    /**
     * @param {{ userId: string, username: string, displayName: string, count: number }} chatter
     */
    chatter => {
      if (!selectedSessionId || !chatter.userId) return;
      setDrawerState({
        isOpen: true,
        title: `Mensajes de ${chatter.displayName}`,
        subtitle:
          chatter.username && chatter.displayName.toLowerCase() !== chatter.username.toLowerCase()
            ? `@${chatter.username} · ${chatter.count} mensajes en la sesión`
            : `${chatter.count} mensajes en la sesión`,
        since: null,
        until: null,
        userId: chatter.userId,
      });
    },
    [selectedSessionId]
  );

  const handleCloseDrawer = useCallback(() => {
    setDrawerState(prev => ({ ...prev, isOpen: false }));
  }, []);

  // Manejo de cambio de intervalo desde la cabecera de ChatActivityChart
  const handleChangeChatInterval = useCallback(
    /** @param {number} newInterval */
    newInterval => {
      const intervalNum = Number(newInterval) || 5;
      setChatInterval(intervalNum);
      if (chatIntervalControllerRef.current) {
        chatIntervalControllerRef.current.abort();
      }
      if (!selectedSessionId) return;

      const controller = new AbortController();
      chatIntervalControllerRef.current = controller;
      const { signal } = controller;

      apiGet(
        `/api/analytics/chat_activity?stream_id=${encodeURIComponent(
          selectedSessionId
        )}&interval_minutes=${intervalNum}`,
        { signal }
      )
        .then(res => {
          if (isMountedRef.current && !signal.aborted && res && res.ok !== false) {
            const payload = res.data ?? res;
            setChatActivity(
              Array.isArray(payload) ? payload : payload.activity || payload.data || []
            );
          }
        })
        .catch(() => {});
    },
    [selectedSessionId]
  );

  // Refresco manual
  const handleRefresh = useCallback(() => {
    fetchAnalyticsData(selectedSessionId, chatInterval, true);
  }, [selectedSessionId, chatInterval, fetchAnalyticsData]);

  // Auto-refresco cada 30s si la sesión seleccionada está en vivo
  useEffect(() => {
    if (!currentSession || !currentSession.is_live) return;

    const timer = setInterval(() => {
      fetchAnalyticsData(selectedSessionId, chatInterval, true);
    }, 30000);

    return () => clearInterval(timer);
  }, [currentSession, selectedSessionId, chatInterval, fetchAnalyticsData]);

  const hasData =
    sessions.length > 0 ||
    overview != null ||
    viewersTimeline.length > 0 ||
    chatActivity.length > 0 ||
    topChatters.length > 0;

  return html`
    <div class="analytics-tab">
      <${AnalyticsFilterBar}
        sessions=${sessions}
        selectedSessionId=${selectedSessionId}
        onSelectSession=${handleSelectSession}
        onRefresh=${handleRefresh}
        loading=${refreshing || loading}
      />

      <div class="analytics-tab-scrollable">
        ${
          error
            ? html`
                <div class="analytics-error-banner" role="alert">
                  <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                  <span>${error}</span>
                  <button type="button" class="analytics-retry-btn" onClick=${handleRefresh}>
                    Reintentar
                  </button>
                </div>
              `
            : null
        }
        ${
          loading
            ? html`<${AnalyticsSkeleton} />`
            : !hasData
              ? html`<${AnalyticsEmptyState} onRefresh=${handleRefresh} />`
              : html`
                  <${AnalyticsSummaryCards}
                    overview=${overview || {}}
                    currentSession=${currentSession}
                    canOpenFollowersDetail=${Boolean(selectedSessionId)}
                    onOpenFollowersDetail=${() => {
                      if (selectedSessionId) setFollowersDrawerOpen(true);
                    }}
                  />

                  <div class="analytics-charts-grid">
                    <${ViewersTimelineChart} data=${viewersTimeline} session=${currentSession} />
                    <${ChatActivityChart}
                      data=${chatActivity}
                      interval=${chatInterval}
                      onIntervalChange=${handleChangeChatInterval}
                      onSelectBucket=${handleSelectBucket}
                    />
                    <${TopChattersChart}
                      data=${topChatters}
                      onSelectChatter=${handleSelectChatter}
                    />
                    <${StreamEventsChart} data=${streamEvents} session=${currentSession} />
                  </div>
                `
        }
      </div>

      <${AnalyticsMessagesDrawer}
        isOpen=${drawerState.isOpen}
        onClose=${handleCloseDrawer}
        streamId=${selectedSessionId}
        title=${drawerState.title}
        subtitle=${drawerState.subtitle}
        since=${drawerState.since}
        until=${drawerState.until}
        userId=${drawerState.userId}
      />

      <${AnalyticsFollowersDrawer}
        isOpen=${followersDrawerOpen}
        onClose=${() => setFollowersDrawerOpen(false)}
        streamId=${selectedSessionId}
        sessionTitle=${currentSession && currentSession.title ? String(currentSession.title) : ''}
      />
    </div>
  `;
}
