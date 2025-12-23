from __future__ import annotations

from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input

from src.dashboard.data_sources import DashboardConfigProtocol


def register_aliases_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        dash.Output("vdm-aliases-content", "children"),
        Input("vdm-aliases-poll", "n_intervals"),
        Input("vdm-aliases-refresh", "n_clicks"),
        Input("vdm-aliases-search", "value"),
        prevent_initial_call=False,
    )
    def refresh_aliases(
        _n: int,
        _clicks: int | None,
        search_term: str | None,
    ) -> Any:
        try:
            from src.dashboard.services.aliases import build_aliases_view

            view = run(build_aliases_view(cfg=cfg, search_term=search_term))
            return view.content

        except Exception as e:
            return dbc.Alert(f"Failed to load aliases: {e}", color="danger")
