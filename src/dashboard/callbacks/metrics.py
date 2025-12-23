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
        Output("vdm-provider-breakdown", "children"),
        Output("vdm-model-breakdown", "children"),
        Output("vdm-provider-filter", "options"),
        Input("vdm-metrics-poll", "n_intervals"),
        Input("vdm-provider-filter", "value"),
        Input("vdm-model-filter", "value"),
        State("vdm-metrics-poll-toggle", "value"),
        prevent_initial_call=False,
    )
    def refresh_metrics(
        n: int,
        provider_value: str,
        model_value: str,
        polling: bool,
    ) -> tuple[Any, Any, Any, Any]:
        if not polling and n:
            raise dash.exceptions.PreventUpdate

        from src.dashboard.services.metrics import build_metrics_view

        view = run(
            build_metrics_view(cfg=cfg, provider_value=provider_value, model_value=model_value)
        )
        return (
            view.token_chart,
            view.provider_breakdown,
            view.model_breakdown,
            view.provider_options,
        )

    @app.callback(Output("vdm-metrics-poll", "interval"), Input("vdm-metrics-interval", "value"))
    def set_metrics_interval(ms: int) -> int:
        return ms
