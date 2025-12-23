from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.components.ui import model_details_drawer, models_table


def models_layout() -> dbc.Container:
    """Layout for the Models page.

    Filtering and sorting are handled directly in the AG-Grid table.
    """

    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.H2("Available Models"), md=6),
                    dbc.Col(
                        dbc.Stack(
                            [
                                dbc.Label("Provider", className="text-muted small mb-0"),
                                dcc.Dropdown(
                                    id="vdm-models-provider",
                                    options=[],
                                    value=None,
                                    placeholder="Provider",
                                    clearable=False,
                                    style={"minWidth": "14rem"},
                                ),
                            ],
                            gap=1,
                        ),
                        md=3,
                    ),
                    dbc.Col(
                        dbc.ButtonGroup(
                            [
                                dbc.Button(
                                    "Copy selected IDs",
                                    id="vdm-models-copy-ids",
                                    color="primary",
                                    outline=False,
                                    size="sm",
                                ),
                                dbc.Button(
                                    "Refresh",
                                    id="vdm-models-refresh",
                                    color="primary",
                                    outline=True,
                                    size="sm",
                                ),
                            ],
                            size="sm",
                        ),
                        md=3,
                        className="text-end",
                    ),
                ],
                className="align-items-center mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Toast(
                            id="vdm-models-copy-toast",
                            header="Models",
                            is_open=False,
                            dismissable=True,
                            duration=4000,
                            icon="success",
                            className="vdm-toast-wide",
                            style={
                                "position": "fixed",
                                "top": 80,
                                "right": 20,
                                "width": 360,
                                "zIndex": 2000,
                            },
                        ),
                        md=12,
                    ),
                ]
            ),
            dcc.Store(id="vdm-models-selected-ids", data=[]),
            dcc.Store(id="vdm-models-detail-store", data=None),
            model_details_drawer(),
            # Hidden sinks used by clientside callbacks.
            html.Div(id="vdm-models-copy-sink", style={"display": "none"}),
            # We use a hidden button click as a reliable trigger (Dash-owned n_clicks).
            dbc.Button(
                "",
                id="vdm-models-toast-trigger",
                n_clicks=0,
                style={"display": "none"},
            ),
            # Payload is stored on window.__vdm_last_toast_payload by injected JS.
            html.Div(id="vdm-models-toast-payload", style={"display": "none"}),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            id="vdm-models-provider-hint",
                            className="text-muted small",
                        ),
                        md=12,
                        className="mb-2",
                    ),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                models_table(
                                    [],
                                    sort_field="id",
                                    sort_desc=False,
                                    show_provider=True,
                                )
                            ],
                            id="vdm-models-content",
                        ),
                        md=12,
                    ),
                ]
            ),
            dcc.Store(id="vdm-models-rowdata", data=[]),
            dcc.Store(id="vdm-models-grid-initialized", data=False),
            # Dedicated rowData output avoids recreating the grid and preserves filters.
            html.Div(id="vdm-models-rowdata-sink", style={"display": "none"}),
            dcc.Interval(id="vdm-models-poll", interval=30_000, n_intervals=0),
        ],
        fluid=True,
        className="py-3",
    )
