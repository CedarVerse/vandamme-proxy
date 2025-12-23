from __future__ import annotations

from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input, Output, html

from src.dashboard.data_sources import DashboardConfigProtocol, fetch_test_connection


def register_overview_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-health-banner", "children"),
        Output("vdm-providers-table", "children"),
        Output("vdm-kpis", "children"),
        Output("vdm-metrics-disabled-callout", "children"),
        Output("vdm-global-error", "children"),
        Input("vdm-overview-poll", "n_intervals"),
        Input("vdm-refresh-now", "n_clicks"),
        prevent_initial_call=False,
    )
    def refresh_overview(_n: int, _clicks: int | None) -> tuple[Any, Any, Any, Any, str]:
        from src.dashboard.services.overview import build_overview_view

        view = run(build_overview_view(cfg=cfg))
        return (
            view.banner,
            view.providers_table,
            view.kpis,
            view.metrics_disabled_callout,
            view.global_error,
        )

    @app.callback(
        Output("vdm-test-connection-result", "children"),
        Input("vdm-test-connection", "n_clicks"),
        prevent_initial_call=True,
    )
    def run_test_connection(n_clicks: int) -> Any:
        _ = n_clicks
        payload = run(fetch_test_connection(cfg=cfg))
        status = str(payload.get("status", "unknown"))
        http_status = payload.get("_http_status", "")

        color = "success" if status == "success" else "danger"
        rows: list[Any] = [
            html.Div(
                [
                    dbc.Badge(status.upper(), color=color, pill=True),
                    html.Span(" "),
                    html.Span(f"HTTP {http_status}"),
                ]
            ),
            html.Div([html.Span("provider: "), html.Span(str(payload.get("provider", "")))]),
            html.Div([html.Span("timestamp: "), html.Span(str(payload.get("timestamp", "")))]),
        ]

        if status == "success":
            rows.append(
                html.Div(
                    [html.Span("response_id: "), html.Code(str(payload.get("response_id", "")))]
                )
            )
        else:
            rows.append(
                html.Div([html.Span("message: "), html.Span(str(payload.get("message", "")))])
            )
            suggestions = payload.get("suggestions")
            if isinstance(suggestions, list) and suggestions:
                rows.append(html.Div("Suggestions", className="text-muted small mt-2"))
                rows.append(html.Ul([html.Li(str(s)) for s in suggestions]))

        return dbc.Alert(rows, color="light", className="mt-2")
