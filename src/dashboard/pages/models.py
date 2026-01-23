from __future__ import annotations

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import dcc, html

from src.dashboard.components.ui import model_details_drawer, models_table


def _provider_tab_content() -> list:
    """Content for provider models tab."""
    return [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Stack(
                        [
                            dbc.Label("Provider", className="text-muted small mb-0"),
                            dcc.Dropdown(
                                id="vdm-models-provider-dropdown",
                                options=[],
                                value=None,
                                placeholder="Provider",
                                clearable=False,
                            ),
                        ],
                        gap=1,
                    ),
                )
            ]
        ),
        html.Div(id="vdm-models-provider-hint", className="text-muted small mb-2"),
        html.Div(id="vdm-models-provider-docs-link", className="mb-3"),
        models_table(
            [],
            sort_field="id",
            sort_desc=False,
            show_provider=True,
            grid_id="vdm-models-provider-grid",
        ),
    ]


def _profile_tab_content() -> list:
    """Content for profile models tab."""
    return [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Stack(
                        [
                            dbc.Label("Profile", className="text-muted small mb-0"),
                            dcc.Dropdown(
                                id="vdm-models-profile-dropdown",
                                options=[],
                                value=None,
                                placeholder="Profile",
                                clearable=False,
                            ),
                        ],
                        gap=1,
                    ),
                )
            ]
        ),
        html.Div(id="vdm-models-profile-hint", className="text-muted small mb-2"),
        models_table(
            [],
            sort_field="id",
            sort_desc=False,
            show_provider=True,
            grid_id="vdm-models-profile-grid",
        ),
    ]


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
                        md=6,
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
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        dbc.Tabs(
                                            [
                                                dbc.Tab(
                                                    _provider_tab_content(),
                                                    label="Provider Models",
                                                    tab_id="provider-tab",
                                                ),
                                                dbc.Tab(
                                                    _profile_tab_content(),
                                                    label="Profile Models",
                                                    tab_id="profile-tab",
                                                ),
                                            ],
                                            id="vdm-models-tabs",
                                            active_tab="provider-tab",
                                        ),
                                    ]
                                ),
                            ]
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
