from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html


def overview_layout() -> dbc.Container:
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.H2("Vandamme Proxy"), md=8),
                    dbc.Col(
                        dbc.Stack(
                            [
                                dbc.Switch(
                                    id="vdm-theme-toggle",
                                    label="Dark mode",
                                    value=True,
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "Refresh now",
                                    id="vdm-refresh-now",
                                    color="secondary",
                                    outline=True,
                                ),
                            ],
                            direction="horizontal",
                            gap=2,
                            className="justify-content-end",
                        ),
                        md=4,
                    ),
                ],
                className="align-items-center mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(html.Div(id="vdm-health-banner"), md=12),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Card(dbc.CardBody(id="vdm-metrics-disabled-callout")), md=12),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Spinner(id="vdm-kpis"), md=12),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Providers"),
                                dbc.CardBody(dbc.Spinner(id="vdm-providers-table")),
                            ]
                        ),
                        md=7,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Upstream connectivity"),
                                dbc.CardBody(
                                    [
                                        dbc.Button(
                                            "Run test connection",
                                            id="vdm-test-connection",
                                            color="primary",
                                        ),
                                        html.Div(className="mt-3", id="vdm-test-connection-result"),
                                    ]
                                ),
                            ]
                        ),
                        md=5,
                    ),
                ],
                className="mb-3",
            ),
            dcc.Interval(id="vdm-overview-poll", interval=10_000, n_intervals=0),
        ],
        fluid=True,
        className="py-3",
    )
