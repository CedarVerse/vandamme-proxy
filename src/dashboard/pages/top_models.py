from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.components.ui import search_box


def top_models_layout() -> dbc.Container:
    """Layout for the Top Models discovery page."""
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.H2("Top Models"), md=6),
                    dbc.Col(
                        dbc.Button(
                            "Refresh",
                            id="vdm-top-models-refresh",
                            color="primary",
                            outline=True,
                            size="sm",
                        ),
                        md=6,
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
                                dbc.CardHeader(html.Strong("Filters", className="text-primary")),
                                dbc.CardBody(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        "Sub-provider", className="text-muted small"
                                                    ),
                                                    dcc.Dropdown(
                                                        id="vdm-top-models-provider",
                                                        options=[{"label": "All", "value": ""}],  # type: ignore[arg-type]
                                                        value="",
                                                        clearable=False,
                                                        className="border-primary",
                                                    ),
                                                ]
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div("Limit", className="text-muted small"),
                                                    dcc.Dropdown(
                                                        id="vdm-top-models-limit",
                                                        options=[
                                                            {"label": "5", "value": 5},
                                                            {"label": "10", "value": 10},
                                                            {"label": "20", "value": 20},
                                                            {"label": "50", "value": 50},
                                                        ],  # type: ignore[arg-type]
                                                        value=10,
                                                        clearable=False,
                                                        className="border-primary",
                                                        style={"minWidth": "6rem"},
                                                    ),
                                                ]
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        "Search", className="text-muted small"
                                                    ),
                                                    search_box(
                                                        "vdm-top-models-search",
                                                        placeholder="Search id or name...",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="g-3 align-items-end",
                                    )
                                ),
                            ]
                        ),
                        md=12,
                    )
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Status"),
                                dbc.CardBody(id="vdm-top-models-status"),
                            ]
                        ),
                        md=4,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Metadata"),
                                dbc.CardBody(id="vdm-top-models-meta"),
                            ]
                        ),
                        md=8,
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Models"),
                                dbc.CardBody(dbc.Spinner(id="vdm-top-models-content")),
                            ]
                        ),
                        md=12,
                    )
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Suggested aliases"),
                                dbc.CardBody(id="vdm-top-models-aliases"),
                            ]
                        ),
                        md=12,
                    )
                ],
                className="mb-3",
            ),
            dcc.Interval(id="vdm-top-models-poll", interval=60_000, n_intervals=0),
        ],
        fluid=True,
        className="py-3",
    )


def top_models_grid_placeholder(*_args: Any, **_kwargs: Any) -> Any:
    """Reserved for potential future split of grid composition."""
    return html.Div()
