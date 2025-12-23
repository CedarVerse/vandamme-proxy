from __future__ import annotations

from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input, Output

from src.dashboard.data_sources import DashboardConfigProtocol


def register_logs_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-logs-disabled-callout", "children"),
        Output("vdm-logs-errors-grid", "rowData"),
        Output("vdm-logs-traces-grid", "rowData"),
        Input("vdm-logs-poll", "n_intervals"),
        prevent_initial_call=False,
    )
    def refresh_logs(_n: int) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            from src.dashboard.services.logs import build_logs_view

            view = run(build_logs_view(cfg=cfg))
            return view.disabled_callout, view.errors_row_data, view.traces_row_data

        except Exception as e:  # noqa: BLE001
            return (
                dbc.Alert(f"Failed to load logs: {e}", color="danger"),
                [],
                [],
            )
