from __future__ import annotations

import logging
from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input, Output, html

from src.dashboard.data_sources import DashboardConfigProtocol

logger = logging.getLogger(__name__)


def register_top_models_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-top-models-content", "children"),
        Output("vdm-top-models-provider", "options"),
        Output("vdm-top-models-status", "children"),
        Output("vdm-top-models-meta", "children"),
        Output("vdm-top-models-aliases", "children"),
        Input("vdm-top-models-poll", "n_intervals"),
        Input("vdm-top-models-refresh", "n_clicks"),
        Input("vdm-top-models-provider", "value"),
        Input("vdm-top-models-limit", "value"),
        Input("vdm-top-models-search", "value"),
        prevent_initial_call=False,
    )
    def refresh_top_models(
        _n: int,
        refresh_clicks: int | None,
        provider_value: str | None,
        limit_value: int | None,
        search_value: str | None,
    ) -> tuple[Any, list[dict[str, str]], Any, Any, Any]:
        try:
            from src.dashboard.services.top_models import build_top_models_view

            view = run(
                build_top_models_view(
                    cfg=cfg,
                    provider_value=provider_value,
                    limit_value=limit_value,
                    search_value=search_value,
                    force_refresh=bool(refresh_clicks),
                )
            )
            return view.content, view.provider_options, view.status, view.meta, view.aliases

        except Exception:
            logger.exception("dashboard.top-models: refresh failed")
            return (
                dbc.Alert(
                    "Failed to load top models. See server logs for details.",
                    color="danger",
                ),
                [{"label": "All", "value": ""}],
                html.Span("Failed", className="text-muted"),
                html.Div(),
                html.Div(),
            )
