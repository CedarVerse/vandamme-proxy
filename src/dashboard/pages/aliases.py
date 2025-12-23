from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.components.ui import search_box


def aliases_layout() -> dbc.Container:
    """Layout for the Aliases page with search and provider grouping."""
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.H2("Model Aliases"), md=8),
                    dbc.Col(
                        dbc.Button(
                            "Refresh",
                            id="vdm-aliases-refresh",
                            color="primary",
                            outline=True,
                            size="sm",
                        ),
                        md=4,
                        className="text-end",
                    ),
                ],
                className="align-items-center mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.Strong("Search", className="text-primary")),
                                dbc.CardBody(search_box("vdm-aliases-search", "Search aliases...")),
                            ]
                        ),
                        md=12,
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Spinner(id="vdm-aliases-content"),
                        md=12,
                    ),
                ],
            ),
            dcc.Interval(id="vdm-aliases-poll", interval=60_000, n_intervals=0),
        ],
        fluid=True,
        className="py-3",
    )
