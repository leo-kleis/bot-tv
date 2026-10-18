import { html, useState, useEffect, useCallback, useMemo, useRef } from 'preact-setup';
import { apiGet } from '/static/components/api.js';
import { AnalyticsFilterBar } from './AnalyticsFilterBar.js';
import { AnalyticsSummaryCards } from './AnalyticsSummaryCards.js';
import { ViewersTimelineChart } from './ViewersTimelineChart.js';
import { ChatActivityChart } from './ChatActivityChart.js';
import { TopChattersChart } from './TopChattersChart.js';
import { FollowersGrowthChart } from './FollowersGrowthChart.js';
import { StreamEventsChart } from './StreamEventsChart.js';
import { AnalyticsSkeleton } from './AnalyticsSkeleton.js';
import { AnalyticsEmptyState } from './AnalyticsEmptyState.js';

export function AnalyticsTab() {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [chatInterval, setChatInterval] = useState(5);
  const [period, setPeriod] = useState('24h');

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Estados de datos de analíticas
  const [overview, setOverview] = useState(null);
  const [viewersTimeline, setViewersTimeline] = useState([]);
  const [chatActivity, setChatActivity] = useState([]);
  const [topChatters, setTopChatters] = useState([]);
  const [followersGrowth, setFollowersGrowth] = useState([]);
  const [streamEvents, setStreamEvents] = useState(null);

  const isMountedRef = useRef(true);
  const batchControllerRef = useRef(null);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (batchControllerRef.current) {
        batchControllerRef.current.abort();
      }
    };
  }, []);

  // Sesión actualmente seleccionada
  const currentSession = useMemo(() => {
    if (!sessions || sessions.length === 0) return null;
    if (selectedSessionId == null) return sessions[0] || null;
    return sessions.find(s => s.id === selectedSessionId) || sessions[0] || null;
  }, [sessions, selectedSessionId]);

  // Carga de todas las métricas en paralelo
  const fetchAnalyticsData = useCallback(
    async (sessionId, interval, currentPeriod, isBackground = false) => {
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
        const streamParam = sessionId ? `?stream_id=${sessionId}` : '';
        const chatParam = sessionId
          ? `?stream_id=${sessionId}&interval_minutes=${interval}`
          : `?interval_minutes=${interval}`;
        const topChattersParam = `?period=${currentPeriod}&limit=10`;
        const growthParam = `?period=day`;

        const [overviewRes, timelineRes, chatRes, chattersRes, growthRes, eventsRes] =
          await Promise.allSettled([
            apiGet('/api/analytics/overview', { signal }),
            sessionId
              ? apiGet(`/api/analytics/viewers_timeline${streamParam}`, { signal })
              : Promise.resolve(null),
            sessionId
              ? apiGet(`/api/analytics/chat_activity${chatParam}`, { signal })
              : Promise.resolve(null),
            apiGet(`/api/analytics/top_chatters${topChattersParam}`, { signal }),
            apiGet(`/api/analytics/followers_growth${growthParam}`, { signal }),
            sessionId
              ? apiGet(`/api/analytics/stream_events${streamParam}`, { signal })
              : Promise.resolve(null),
          ]);

        if (!isMountedRef.current || signal.aborted) return;

        if (
          overviewRes.status === 'fulfilled' &&
          overviewRes.value &&
          overviewRes.value.ok !== false
        ) {
          setOverview(overviewRes.value);
        }
        if (
          timelineRes.status === 'fulfilled' &&
          timelineRes.value &&
          timelineRes.value.ok !== false
        ) {
          setViewersTimeline(
            timelineRes.value.data || timelineRes.value.timeline || timelineRes.value || []
          );
        } else if (sessionId == null) {
          setViewersTimeline([]);
        }
        if (chatRes.status === 'fulfilled' && chatRes.value && chatRes.value.ok !== false) {
          setChatActivity(chatRes.value.data || chatRes.value.activity || chatRes.value || []);
        } else if (sessionId == null) {
          setChatActivity([]);
        }
        if (
          chattersRes.status === 'fulfilled' &&
          chattersRes.value &&
          chattersRes.value.ok !== false
        ) {
          setTopChatters(
            chattersRes.value.chatters || chattersRes.value.data || chattersRes.value || []
          );
        }
        if (growthRes.status === 'fulfilled' && growthRes.value && growthRes.value.ok !== false) {
          setFollowersGrowth(
            growthRes.value.data || growthRes.value.growth || growthRes.value || []
          );
        }
        if (eventsRes.status === 'fulfilled' && eventsRes.value && eventsRes.value.ok !== false) {
          setStreamEvents(
            eventsRes.value.events || eventsRes.value.data || eventsRes.value || null
          );
        } else if (sessionId == null) {
          setStreamEvents(null);
        }
      } catch (err) {
        if (isMountedRef.current && !signal.aborted) {
          setError(err.message || 'Error al obtener datos analíticos');
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
    let active = true;

    async function initSessions() {
      try {
        const res = await apiGet('/api/analytics/stream_sessions');
        if (!active) return;

        if (res && res.ok !== false) {
          const list = res.sessions || res.data || (Array.isArray(res) ? res : []);
          setSessions(list);

          if (list.length > 0) {
            // Priorizar sesión en vivo o la más reciente
            const live = list.find(s => Boolean(s.is_live));
            const initialId = live ? live.id : list[0].id;
            setSelectedSessionId(initialId);
            fetchAnalyticsData(initialId, chatInterval, period);
          } else {
            // No hay sesiones de stream, consultar métricas generales
            fetchAnalyticsData(null, chatInterval, period);
          }
        } else {
          // Si el endpoint de sesiones da error o está vacío, consultar de forma global
          fetchAnalyticsData(null, chatInterval, period);
        }
      } catch (err) {
        if (active) {
          setError(err.message || 'Error al conectar con el servidor');
          setLoading(false);
        }
      }
    }

    initSessions();

    return () => {
      active = false;
    };
  }, [fetchAnalyticsData]);

  // Manejo de cambio de sesión
  const handleSelectSession = useCallback(
    newId => {
      setSelectedSessionId(newId);
      fetchAnalyticsData(newId, chatInterval, period);
    },
    [chatInterval, period, fetchAnalyticsData]
  );

  // Manejo de cambio de intervalo
  const handleChangeChatInterval = useCallback(
    newInterval => {
      setChatInterval(newInterval);
      if (selectedSessionId) {
        // Recargar actividad de chat
        apiGet(
          `/api/analytics/chat_activity?stream_id=${selectedSessionId}&interval_minutes=${newInterval}`
        ).then(res => {
          if (isMountedRef.current && res && res.ok !== false) {
            setChatActivity(res.data || res.activity || res || []);
          }
        });
      }
    },
    [selectedSessionId]
  );

  // Manejo de cambio de período
  const handleChangePeriod = useCallback(newPeriod => {
    setPeriod(newPeriod);
    apiGet(`/api/analytics/top_chatters?period=${newPeriod}&limit=10`).then(res => {
      if (isMountedRef.current && res && res.ok !== false) {
        setTopChatters(res.chatters || res.data || res || []);
      }
    });
  }, []);

  // Refresco manual
  const handleRefresh = useCallback(() => {
    fetchAnalyticsData(selectedSessionId, chatInterval, period, true);
  }, [selectedSessionId, chatInterval, period, fetchAnalyticsData]);

  // Auto-refresco cada 30s si la sesión seleccionada está en vivo
  useEffect(() => {
    if (!currentSession || !currentSession.is_live) return;

    const timer = setInterval(() => {
      fetchAnalyticsData(selectedSessionId, chatInterval, period, true);
    }, 30000);

    return () => clearInterval(timer);
  }, [currentSession, selectedSessionId, chatInterval, period, fetchAnalyticsData]);

  const hasData =
    sessions.length > 0 ||
    overview != null ||
    viewersTimeline.length > 0 ||
    chatActivity.length > 0 ||
    topChatters.length > 0;

  return html`
    <div class="analytics-tab">
      <!-- Barra superior fija de filtros y controles -->
      <${AnalyticsFilterBar}
        sessions=${sessions}
        selectedSessionId=${selectedSessionId}
        onSelectSession=${handleSelectSession}
        chatInterval=${chatInterval}
        onChangeChatInterval=${handleChangeChatInterval}
        period=${period}
        onChangePeriod=${handleChangePeriod}
        onRefresh=${handleRefresh}
        loading=${refreshing || loading}
      />

      <!-- Área desplazable con scroll fluido -->
      <div class="analytics-tab-scrollable">
        ${
          error
            ? html`
                <div class="analytics-error-banner">
                  <i class="fas fa-exclamation-triangle"></i>
                  <span>${error}</span>
                  <button class="analytics-retry-btn" onClick=${handleRefresh}>Reintentar</button>
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
                  <!-- Tarjetas KPI Resumen -->
                  <${AnalyticsSummaryCards}
                    overview=${overview || {}}
                    currentSession=${currentSession}
                  />

                  <!-- Rejilla de Gráficos de Analíticas -->
                  <div class="analytics-charts-grid">
                    <!-- Gráfico 1: Evolución de Espectadores (Full Width) -->
                    <${ViewersTimelineChart} data=${viewersTimeline} session=${currentSession} />

                    <!-- Gráfico 2: Actividad de Mensajes en el Chat -->
                    <${ChatActivityChart} data=${chatActivity} interval=${chatInterval} />

                    <!-- Gráfico 3: Top 10 Participantes del Chat -->
                    <${TopChattersChart} data=${topChatters} period=${period} />

                    <!-- Gráfico 4: Desglose de Eventos del Directo -->
                    <${StreamEventsChart} data=${streamEvents} />

                    <!-- Gráfico 5: Crecimiento Neto de Seguidores -->
                    <${FollowersGrowthChart} data=${followersGrowth} period="day" />
                  </div>
                `
        }
      </div>
    </div>
  `;
}
