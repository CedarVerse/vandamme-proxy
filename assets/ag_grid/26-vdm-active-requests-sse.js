// Vandamme Dashboard - Active Requests SSE Integration
// Consumes SSE stream and updates AG Grid directly without server round-trips.

(function initActiveRequestsSSE() {
    if (window.__vdmActiveRequestsSseInit) return;
    window.__vdmActiveRequestsSseInit = true;

    const GRID_ID = 'vdm-metrics-active-requests-grid';
    const SSE_ENDPOINT_PATTERN = '/metrics/active-requests/stream';

    let eventSource = null;
    let reconnectTimer = null;
    let isSseEnabled = true;

    // Buffer the latest snapshot until the grid API is ready.
    let pendingSnapshot = null;
    let applyPendingTimer = null;
    let reconnectAttempt = 0;

    // Detect API base URL from window.location
    function getApiBaseUrl() {
        // Dashboard is at /dashboard/, API is at root
        const origin = window.location.origin;
        return origin;
    }

    function getSSEUrl() {
        const baseUrl = getApiBaseUrl();
        return `${baseUrl}${SSE_ENDPOINT_PATTERN}`;
    }

    // Provider badge color mapping (must match Python: provider_badge_color)
    function getProviderBadgeColor(provider) {
        const key = (provider || '').toLowerCase();
        const colors = {
            'openai': 'primary',
            'openrouter': 'info',
            'anthropic': 'danger',
            'poe': 'success',
        };
        return colors[key] || 'secondary';
    }

    // Transform API row data to AG Grid rowData format
    // Matches Python: metrics_active_requests_row_data() in transformers.py
    function formatActiveRequestsRowData(apiRow) {
        if (!apiRow || typeof apiRow !== 'object') return null;

        const provider = apiRow.provider || 'unknown';
        const model = apiRow.model || '';
        const startTime = apiRow.start_time || 0;
        const startTimeMs = startTime < 1e12 ? (startTime * 1000) : startTime;
        const now = Date.now();
        const ageS = Math.max(0, (now - startTimeMs) / 1000);

        return {
            request_id: apiRow.request_id || '',
            provider: provider,
            provider_color: getProviderBadgeColor(provider),
            model: model,
            resolved_model: apiRow.resolved_model || '',
            qualified_model: apiRow.qualified_model || '',
            is_streaming: Boolean(apiRow.is_streaming),
            input_tokens: apiRow.input_tokens || 0,
            output_tokens: apiRow.output_tokens || 0,
            cache_read_tokens: apiRow.cache_read_tokens || 0,
            cache_creation_tokens: apiRow.cache_creation_tokens || 0,
            tool_calls: apiRow.tool_calls || 0,
            tool_uses: apiRow.tool_uses || 0,
            tool_results: apiRow.tool_results || 0,
            request_size: apiRow.request_size || 0,
            message_count: apiRow.message_count || 0,
            // Recency renderer fields
            last_accessed: '',
            last_accessed_iso: new Date(startTimeMs).toISOString(),
            last_accessed_epoch_ms: startTimeMs,
            last_accessed_age_s_at_render: ageS,
        };
    }

    function getGridApi() {
        const dag = window.dash_ag_grid;
        if (!dag || !dag.getApi) return null;
        return dag.getApi(GRID_ID);
    }

    function scheduleApplyPendingSnapshot() {
        if (applyPendingTimer) return;

        let attempt = 0;
        const maxAttempts = 40; // ~10s with backoff below

        function tick() {
            applyPendingTimer = null;
            if (!pendingSnapshot) return;

            const api = getGridApi();
            if (!api) {
                attempt += 1;
                if (attempt > maxAttempts) {
                    console.warn('[vdm][sse] Grid API not ready; dropping pending snapshot');
                    pendingSnapshot = null;
                    return;
                }

                const delay = Math.min(250, 25 * Math.pow(1.35, attempt));
                applyPendingTimer = setTimeout(tick, delay);
                return;
            }

            const snapshot = pendingSnapshot;
            pendingSnapshot = null;
            applySnapshotToGrid(api, snapshot);
        }

        applyPendingTimer = setTimeout(tick, 0);
    }

    function applySnapshotToGrid(api, activeRequests) {
        if (!Array.isArray(activeRequests)) return;

        // Shape + validate + de-dupe by request_id.
        // We must never feed the grid duplicate IDs, otherwise AG Grid can end up with
        // empty/ghost rows and "duplicate node id" errors.
        const byId = new Map();
        for (const raw of activeRequests) {
            const row = formatActiveRequestsRowData(raw);
            if (!row) continue;

            const id = row.request_id;
            if (!id || typeof id !== 'string') continue;

            // Keep the newest copy if duplicates occur (shouldn't happen, but defensive).
            // Prefer larger last_accessed_epoch_ms.
            const prev = byId.get(id);
            if (!prev || (row.last_accessed_epoch_ms || 0) >= (prev.last_accessed_epoch_ms || 0)) {
                byId.set(id, row);
            }
        }

        // Stable ordering: most recent first.
        const rowData = Array.from(byId.values()).sort((a, b) => {
            return (b.last_accessed_epoch_ms || 0) - (a.last_accessed_epoch_ms || 0);
        });

        // Reliability-first strategy: replace the grid's entire dataset.
        // With getRowId configured server-side, AG Grid will reuse row nodes, avoid
        // duplicate IDs, and correctly remove rows without transactional edge cases.
        try {
            api.setGridOption('rowData', rowData);
        } catch (e) {
            // Fallback for older AG Grid APIs.
            try {
                api.setRowData(rowData);
            } catch (e2) {
                console.warn('[vdm][sse] Failed to set rowData:', e2);
            }
        }
    }

    function updateGrid(activeRequests) {
        // Always buffer latest snapshot; apply when the grid becomes available.
        pendingSnapshot = activeRequests;
        scheduleApplyPendingSnapshot();
    }

    function onMessage(event) {
        if (event.type === 'disabled') {
            console.info('[vdm][sse] Metrics disabled, falling back to polling');
            isSseEnabled = false;  // Prevent reconnection attempts
            disconnectSSE();
            return;
        }

        if (event.type === 'update') {
            try {
                const data = JSON.parse(event.data);
                if (data.active_requests) {
                    updateGrid(data.active_requests);
                }
            } catch (e) {
                console.error('[vdm][sse] Failed to parse update:', e);
            }
        }
    }

    function connectSSE() {
        if (eventSource || !isSseEnabled) return;

        const url = getSSEUrl();
        console.log('[vdm][sse] Connecting to', url);

        try {
            eventSource = new EventSource(url);

            eventSource.addEventListener('update', onMessage);
            eventSource.addEventListener('disabled', onMessage);

            eventSource.onopen = () => {
                reconnectAttempt = 0;
                console.log('[vdm][sse] Connected');
                updateConnectionIndicator(true);
            };

            eventSource.onerror = (e) => {
                updateConnectionIndicator(false);

                // EventSource auto-reconnects in most cases.
                // If it has fully closed, we recreate it with a backoff.
                if (eventSource && eventSource.readyState === EventSource.CLOSED) {
                    try { eventSource.close(); } catch (_) {}
                    eventSource = null;

                    reconnectAttempt += 1;
                    const base = Math.min(30000, 750 * Math.pow(1.6, reconnectAttempt));
                    const jitter = base * 0.25 * (Math.random() * 2 - 1);
                    const delay = Math.max(250, base + jitter);

                    if (reconnectTimer) clearTimeout(reconnectTimer);
                    reconnectTimer = setTimeout(connectSSE, delay);
                }

                // Keep the console quieter: EventSource onerror fires frequently during reconnect.
                if (reconnectAttempt <= 1) {
                    console.warn('[vdm][sse] Connection error (will retry)');
                }
            };
        } catch (e) {
            console.error('[vdm][sse] Failed to create EventSource:', e);
            eventSource = null;
            updateConnectionIndicator(false);
        }
    }

    function disconnectSSE() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        updateConnectionIndicator(false);
    }

    function updateConnectionIndicator(connected) {
        // Update toolbar indicator
        const indicator = document.getElementById('vdm-sse-connection-indicator');
        if (indicator) {
            indicator.textContent = connected ? '● Live' : '○ Reconnecting...';
            indicator.style.color = connected ? '#28a745' : '#dc3545';
        }
    }

    // Expose controls for Dash clientside callbacks
    window.__vdmActiveRequestsSSE = {
        enable: () => {
            isSseEnabled = true;
            connectSSE();
        },
        disable: () => {
            isSseEnabled = false;
            disconnectSSE();
        },
        isConnected: () => eventSource && eventSource.readyState === EventSource.OPEN,
    };

    // Auto-connect when page is visible and on metrics page
    function maybeConnect() {
        if (!isSseEnabled) return;

        const gridEl = document.getElementById(GRID_ID);
        if (gridEl && document.visibilityState === 'visible') {
            connectSSE();
        }
    }

    // Watch for page changes (SPA navigation)
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    function checkLocation() {
        if (window.location.pathname.includes('/dashboard/metrics')) {
            maybeConnect();
        } else {
            disconnectSSE();
        }
    }

    if (originalPushState) {
        history.pushState = function() {
            originalPushState.apply(this, arguments);
            checkLocation();
        };
    }
    if (originalReplaceState) {
        history.replaceState = function() {
            originalReplaceState.apply(this, arguments);
            checkLocation();
        };
    }

    window.addEventListener('popstate', checkLocation);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            maybeConnect();
        }
    });

    // Initial connection attempts (deferred to ensure DOM is ready)
    setTimeout(maybeConnect, 100);
    setTimeout(maybeConnect, 1000);

    console.log('[vdm][sse] Active Requests SSE module loaded');
})();
