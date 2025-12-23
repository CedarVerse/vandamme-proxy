from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html


def token_counter_layout() -> dbc.Container:
    """Layout for the Token Counter tool with real-time counting."""
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.H2("Token Counter"), md=12),
                ],
                className="mb-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.Strong("Configuration")),
                                dbc.CardBody(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Label("Model", className="form-label"),
                                                    dcc.Dropdown(
                                                        id="vdm-token-counter-model",
                                                        placeholder="Select a model...",
                                                        clearable=False,
                                                        className="border-primary",
                                                    ),
                                                    html.Div(
                                                        [
                                                            "Model list loads automatically;",
                                                            " select to enable counting.",
                                                        ],
                                                        className="text-muted small mt-1",
                                                    ),
                                                ]
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Label(
                                                        "System Message (Optional)",
                                                        className="form-label",
                                                    ),
                                                    dbc.Textarea(
                                                        id="vdm-token-counter-system",
                                                        placeholder="Enter system message...",
                                                        rows=3,
                                                        className="mb-3",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="g-3",
                                    )
                                ),
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
                                dbc.CardHeader(html.Strong("Message")),
                                dbc.CardBody(
                                    [
                                        dbc.Textarea(
                                            id="vdm-token-counter-message",
                                            placeholder=(
                                                "Enter your message here to count tokens..."
                                            ),
                                            rows=10,
                                            className="mb-3",
                                        ),
                                        html.Div(
                                            "Token estimate uses a quick approximation (chars/4).",
                                            className="text-muted small mb-2",
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Button(
                                                        "Clear",
                                                        id="vdm-token-counter-clear",
                                                        color="primary",
                                                        outline=True,
                                                        size="sm",
                                                    ),
                                                    width="auto",
                                                ),
                                                dbc.Col(
                                                    html.Div(id="vdm-token-counter-result"),
                                                    width="auto",
                                                    className="text-end",
                                                ),
                                            ],
                                            className="align-items-center",
                                        ),
                                    ]
                                ),
                            ]
                        ),
                        md=12,
                    ),
                ],
            ),
        ],
        fluid=True,
        className="py-3",
    )
