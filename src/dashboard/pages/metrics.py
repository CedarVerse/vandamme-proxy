from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.normalize import (
    MetricTotals,
    model_rows_for_provider,
    parse_metric_totals,
    provider_rows,
)


def metrics_layout() -> dbc.Container:
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            dbc.Button(
                                "Refresh",
                                id="vdm-metrics-refresh",
                                color="secondary",
                                outline=True,
                                className="me-2",
                                size="sm",
                            ),
                            html.Span(
                                "Polling",
                                className="text-muted small me-1",
                                style={"alignSelf": "center"},
                            ),
                            dbc.Switch(
                                id="vdm-metrics-poll-toggle",
                                value=True,
                                className="me-3",
                            ),
                            html.Span(
                                ["Poll", html.Span(":", className="text-muted ms-1 me-1")],
                                className="small me-1",
                                style={"alignSelf": "center"},
                            ),
                            dcc.Dropdown(
                                id="vdm-metrics-interval",
                                options=[
                                    {"label": "5s", "value": 5_000},
                                    {"label": "10s", "value": 10_000},
                                    {"label": "30s", "value": 30_000},
                                ],  # type: ignore[arg-type]
                                value=5_000,
                                clearable=False,
                                style={"minWidth": "6rem"},
                                className="me-3",
                            ),
                            html.Span(
                                ["Tick", html.Span(":", className="text-muted ms-1 me-1")],
                                className="small me-1",
                                style={"alignSelf": "center"},
                            ),
                            dcc.Dropdown(
                                id="vdm-active-requests-tick-ms",
                                options=[
                                    {"label": "0.5s", "value": 500},
                                    {"label": "1s", "value": 1_000},
                                    {"label": "2s", "value": 2_000},
                                    {"label": "5s", "value": 5_000},
                                ],  # type: ignore[arg-type]
                                value=2_000,
                                clearable=False,
                                style={"minWidth": "5.5rem"},
                            ),
                        ],
                        className="vdm-toolbar justify-content-end py-1",
                    ),
                    md=12,
                ),
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Active requests"),
                                dbc.CardBody(dbc.Spinner(id="vdm-active-requests")),
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
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    [
                                        html.Span("Model aggregates"),
                                        html.Span(
                                            "· Last updated on refresh or polling",
                                            className="text-muted small ms-2",
                                        ),
                                    ]
                                ),
                                dbc.CardBody(dbc.Spinner(id="vdm-model-breakdown")),
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
                                dbc.CardHeader("Provider breakdown"),
                                dbc.CardBody(dbc.Spinner(id="vdm-provider-breakdown")),
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
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    title="Token composition",
                                    children=dbc.CardBody(dbc.Spinner(id="vdm-token-chart")),
                                ),
                            ],
                            start_collapsed=True,
                            className="mb-3",
                        ),
                        md=12,
                    )
                ],
                className="mb-3",
            ),
            dcc.Interval(id="vdm-metrics-poll", interval=5_000, n_intervals=0),
            dcc.Interval(id="vdm-metrics-user-active-poll", interval=500, n_intervals=0),
            dcc.Store(id="vdm-metrics-user-active", data=False),
        ],
        fluid=True,
        className="py-3",
    )


def compute_metrics_views(
    running_totals: dict[str, Any], selected_provider: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prov_rows = provider_rows(running_totals)

    model_rows: list[dict[str, Any]] = []
    if selected_provider:
        chosen = next((r for r in prov_rows if r.get("provider") == selected_provider), None)
        if chosen:
            model_rows = model_rows_for_provider(chosen)

    return prov_rows, model_rows


def parse_totals_for_chart(running_totals: dict[str, Any]) -> MetricTotals:
    return parse_metric_totals(running_totals)


def token_composition_chart(totals: MetricTotals) -> dcc.Graph:
    import plotly.graph_objects as go  # type: ignore[import-untyped]

    labels = ["input", "output", "cache_read", "cache_creation"]
    values = [
        totals.total_input_tokens,
        totals.total_output_tokens,
        totals.cache_read_tokens,
        totals.cache_creation_tokens,
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.6,
                sort=False,
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        height=260,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})
