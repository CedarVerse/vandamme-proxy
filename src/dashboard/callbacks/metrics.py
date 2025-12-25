from __future__ import annotations

from typing import Any

import dash
from dash import Input, Output, State

from src.dashboard.data_sources import DashboardConfigProtocol


def register_metrics_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-token-chart", "children"),
        Output("vdm-active-requests", "children"),
        Output("vdm-provider-breakdown", "children"),
        Output("vdm-model-breakdown", "children"),
        Input("vdm-metrics-poll", "n_intervals"),
        Input("vdm-metrics-refresh", "n_clicks"),
        State("vdm-metrics-poll-toggle", "value"),
        prevent_initial_call=False,
    )
    def refresh_metrics(
        n: int,
        refresh_clicks: int | None,
        polling: bool,
    ) -> tuple[Any, Any, Any, Any]:
        # Manual refresh should always work. Polling can be disabled.
        if not refresh_clicks and (not polling) and n:
            raise dash.exceptions.PreventUpdate

        from src.dashboard.services.metrics import build_metrics_view

        view = run(build_metrics_view(cfg=cfg))
        return (
            view.token_chart,
            view.active_requests,
            view.provider_breakdown,
            view.model_breakdown,
        )

    @app.callback(Output("vdm-metrics-poll", "interval"), Input("vdm-metrics-interval", "value"))
    def set_metrics_interval(ms: int) -> int:
        return ms

    app.clientside_callback(
        """
        function(n) {
            // Active Requests duration text ticker: fixed at 1s.
            // This is purely client-side UI (no server polling).
            window.__vdm_active_requests_duration_tick_ms = 1000;
            try {
                if (window.localStorage) {
                    localStorage.setItem('vdm.metrics.activeRequests.durationTickMs', '1000');
                }
            } catch (e) {
                // ignore
            }

            if (window.dash_clientside
                && window.dash_clientside.vdm_metrics
                && window.dash_clientside.vdm_metrics.user_active) {
                return window.dash_clientside.vdm_metrics.user_active(n);
            }
            return false;
        }
        """,
        Output("vdm-metrics-user-active", "data"),
        Input("vdm-metrics-user-active-poll", "n_intervals"),
        prevent_initial_call=False,
    )

    app.clientside_callback(
        """
        function(n) {
            // Report SSE connection state to Dash.
            // (We tick this on the existing 500ms user-active interval.)
            if (window.__vdmActiveRequestsSSE) {
                return {
                    'connected': window.__vdmActiveRequestsSSE.isConnected(),
                    'supported': true,
                };
            }
            return { 'connected': false, 'supported': false };
        }
        """,
        Output("vdm-sse-state", "data"),
        Input("vdm-metrics-user-active-poll", "n_intervals"),
        prevent_initial_call=False,
    )

    app.clientside_callback(
        """
        function(n) {
            // Dedicated SSE indicator state for the Active Requests card.
            return Boolean(
                window.__vdmActiveRequestsSSE
                && window.__vdmActiveRequestsSSE.isConnected
                && window.__vdmActiveRequestsSSE.isConnected()
            );
        }
        """,
        Output("vdm-active-requests-sse-live", "data"),
        Input("vdm-active-requests-sse-indicator-tick", "n_intervals"),
        prevent_initial_call=False,
    )

    @app.callback(
        Output("vdm-active-requests-sse-indicator", "children"),
        Output("vdm-active-requests-sse-indicator", "style"),
        Output("vdm-active-requests-sse-indicator", "title"),
        Input("vdm-active-requests-sse-live", "data"),
    )
    def render_active_requests_sse_indicator(is_live: bool) -> tuple[str, dict[str, object], str]:
        """Show a clear live indicator for the Active Requests SSE stream."""

        if is_live:
            return (
                "📡",
                {"opacity": 1.0, "filter": "grayscale(0%)", "cursor": "help"},
                "Live: Active Requests updates via SSE (real-time)",
            )
        return (
            "⚫",
            {"opacity": 0.35, "filter": "grayscale(100%)", "cursor": "help"},
            "Disconnected: Active Requests using polling fallback",
        )

    @app.callback(
        Output("vdm-metrics-poll", "disabled"),
        Input("vdm-metrics-user-active", "data"),
        State("vdm-metrics-poll-toggle", "value"),
    )
    def control_polling_state(user_active: bool, polling_enabled: bool) -> bool:
        """Control polling state based on user activity and polling toggle.

        IMPORTANT: We do NOT disable polling when SSE is connected.
        Reason: SSE only updates the Active Requests grid. Other grids (Provider breakdown,
        Model aggregates, Token composition) still need polling updates. Disabling the
        poll interval when SSE is live would starve those other grids of updates.

        Polling is disabled when:
        - User is actively interacting (to avoid jitter)
        - Polling toggle is manually off

        Returns True if polling should be disabled, False otherwise.
        """
        # Disable if user is interacting or polling is manually off
        return (not polling_enabled) or bool(user_active)
