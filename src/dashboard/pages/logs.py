from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html


def logs_layout() -> dbc.Container:
    """Layout for the Logs page with AG-Grid tables."""
    from src.dashboard.components.ag_grid import logs_errors_ag_grid, logs_traces_ag_grid

    return dbc.Container(
        [
            dbc.Row([dbc.Col(html.H2("Logs"), md=12)], className="mb-4"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.Strong("Recent")),
                                dbc.CardBody(
                                    [
                                        html.Div(id="vdm-logs-disabled-callout"),
                                        dbc.Tabs(
                                            [
                                                dbc.Tab(
                                                    [
                                                        # Grid created once.
                                                        # Row data updated via callback.
                                                        logs_errors_ag_grid(
                                                            [], grid_id="vdm-logs-errors-grid"
                                                        ),
                                                    ],
                                                    label="Errors",
                                                    tab_id="errors-tab",
                                                ),
                                                dbc.Tab(
                                                    [
                                                        # Grid created once.
                                                        # Row data updated via callback.
                                                        logs_traces_ag_grid(
                                                            [], grid_id="vdm-logs-traces-grid"
                                                        ),
                                                    ],
                                                    label="Traces",
                                                    tab_id="traces-tab",
                                                ),
                                            ],
                                            id="vdm-logs-tabs",
                                            active_tab="errors-tab",
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        md=12,
                    )
                ],
                className="mb-3",
            ),
            dcc.Interval(id="vdm-logs-poll", interval=5_000, n_intervals=0),
        ],
        fluid=True,
        className="py-3",
    )
