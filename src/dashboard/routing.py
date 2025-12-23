from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.pages import (
    aliases_layout,
    logs_layout,
    metrics_layout,
    models_layout,
    overview_layout,
    token_counter_layout,
    top_models_layout,
)


def render_page_for_path(pathname: str | None) -> Any:
    if pathname in (None, "/dashboard", "/dashboard/"):
        return overview_layout()
    if pathname in ("/dashboard/metrics", "/dashboard/metrics/"):
        return metrics_layout()
    if pathname in ("/dashboard/models", "/dashboard/models/"):
        return models_layout()
    if pathname in ("/dashboard/top-models", "/dashboard/top-models/"):
        return top_models_layout()
    if pathname in ("/dashboard/aliases", "/dashboard/aliases/"):
        return aliases_layout()
    if pathname in ("/dashboard/token-counter", "/dashboard/token-counter/"):
        return token_counter_layout()
    if pathname in ("/dashboard/logs", "/dashboard/logs/"):
        return logs_layout()

    return dbc.Container(
        dbc.Alert(
            [html.Div("Not found"), html.Div(dcc.Link("Back", href="/dashboard/"))],
            color="secondary",
        ),
        className="py-3",
        fluid=True,
    )
