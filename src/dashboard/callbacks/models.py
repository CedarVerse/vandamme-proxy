from __future__ import annotations

import json
import logging
from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input, Output, State, html

from src.dashboard.components.ui import monospace, provider_badge
from src.dashboard.data_sources import DashboardConfigProtocol

logger = logging.getLogger(__name__)


def register_models_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-models-provider-grid", "rowData"),
        Output("vdm-models-provider-dropdown", "options"),
        Output("vdm-models-provider-dropdown", "value"),
        Output("vdm-models-provider-hint", "children"),
        Input("vdm-models-poll", "n_intervals"),
        Input("vdm-models-refresh", "n_clicks"),
        Input("vdm-models-provider-dropdown", "value"),
        prevent_initial_call=False,
    )
    def refresh_provider_models(
        _n: int,
        _clicks: int | None,
        provider_value: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None, Any]:
        """Fetch and update provider models tab."""
        try:
            from src.dashboard.services.models import build_provider_models_view

            view = run(build_provider_models_view(cfg=cfg, provider_value=provider_value))
            return view.row_data, view.provider_options, view.provider_value, view.hint

        except Exception:
            logger.exception("dashboard.models: provider refresh failed")
            return (
                [],
                [],
                None,
                html.Span("Failed to load providers", className="text-muted"),
            )

    @app.callback(
        Output("vdm-models-profile-grid", "rowData"),
        Output("vdm-models-profile-dropdown", "options"),
        Output("vdm-models-profile-dropdown", "value"),
        Output("vdm-models-profile-hint", "children"),
        Input("vdm-models-poll", "n_intervals"),
        Input("vdm-models-refresh", "n_clicks"),
        Input("vdm-models-profile-dropdown", "value"),
        prevent_initial_call=False,
    )
    def refresh_profile_models(
        _n: int,
        _clicks: int | None,
        profile_value: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None, Any]:
        """Fetch and update profile models tab."""
        try:
            from src.dashboard.services.models import build_profile_models_view

            view = run(build_profile_models_view(cfg=cfg, profile_value=profile_value))
            return view.row_data, view.profile_options, view.profile_value, view.hint

        except Exception:
            logger.exception("dashboard.models: profile refresh failed")
            return (
                [],
                [],
                None,
                html.Span("Failed to load profiles", className="text-muted"),
            )

    @app.callback(
        Output("vdm-models-detail-store", "data"),
        Output("vdm-model-details-drawer", "is_open"),
        Input("vdm-models-provider-grid", "selectedRows"),
        Input("vdm-models-profile-grid", "selectedRows"),
        Input("vdm-model-details-close", "n_clicks"),
        State("vdm-model-details-drawer", "is_open"),
        prevent_initial_call=True,
    )
    def set_model_details_state(
        provider_selected_rows: list[dict[str, Any]] | None,
        profile_selected_rows: list[dict[str, Any]] | None,
        _close_clicks: int | None,
        _is_open: bool,
    ) -> tuple[Any, bool]:
        trigger = dash.callback_context.triggered_id

        if trigger == "vdm-model-details-close":
            return None, False

        # Determine which grid triggered the callback based on trigger_id
        if trigger == "vdm-models-provider-grid":
            selected_rows = provider_selected_rows
        elif trigger == "vdm-models-profile-grid":
            selected_rows = profile_selected_rows
        else:
            selected_rows = None

        rows = selected_rows or []
        if not rows:
            return None, False

        focused = rows[0] if isinstance(rows[0], dict) else None
        return {"focused": focused, "selected_count": len(rows)}, True

    @app.callback(
        Output("vdm-model-details-header", "children"),
        Output("vdm-model-details-body", "children"),
        Input("vdm-models-detail-store", "data"),
        prevent_initial_call=True,
    )
    def render_model_details(detail_store: dict[str, Any] | None) -> tuple[Any, Any]:
        if not isinstance(detail_store, dict):
            return html.Div(), html.Div()

        focused = detail_store.get("focused")
        if not isinstance(focused, dict):
            return html.Div(), html.Div()

        selected_count = detail_store.get("selected_count")
        selected_count_i = int(selected_count) if isinstance(selected_count, int) else None

        model_id = str(focused.get("id") or "")
        provider = str(focused.get("provider") or "")
        owned_by = focused.get("owned_by")
        modality = focused.get("architecture_modality")
        context_length = focused.get("context_length")
        max_output_tokens = focused.get("max_output_tokens")
        created_iso = focused.get("created_iso")
        description_full = focused.get("description_full")
        pricing_in = focused.get("pricing_prompt_per_million")
        pricing_out = focused.get("pricing_completion_per_million")
        model_page_url = focused.get("model_page_url")
        model_icon_url = focused.get("model_icon_url")

        raw_json_obj = {
            k: v for k, v in focused.items() if k not in {"description_full", "description_preview"}
        }
        raw_json = json.dumps(raw_json_obj, sort_keys=True, indent=2, ensure_ascii=False)
        raw_json_preview = "\n".join(raw_json.splitlines()[:40])
        if len(raw_json_preview) < len(raw_json):
            raw_json_preview = raw_json_preview + "\n..."

        title_left_bits: list[Any] = []
        if provider:
            title_left_bits.append(provider_badge(provider))
        title_left_bits.append(html.Span(monospace(model_id), className="fw-semibold"))
        if selected_count_i and selected_count_i > 1:
            title_left_bits.append(
                dbc.Badge(
                    f"Showing 1 of {selected_count_i} selected",
                    color="secondary",
                    pill=True,
                    className="ms-2",
                )
            )

        icon = (
            html.Img(
                src=str(model_icon_url),
                style={
                    "width": "96px",
                    "height": "96px",
                    "objectFit": "contain",
                    "borderRadius": "10px",
                    "backgroundColor": "rgba(255,255,255,0.06)",
                    "padding": "8px",
                },
            )
            if isinstance(model_icon_url, str) and model_icon_url
            else html.Div(
                style={"width": "96px", "height": "96px"},
            )
        )

        header = dbc.Row(
            [
                dbc.Col(icon, width="auto"),
                dbc.Col(html.Div(title_left_bits), width=True),
                dbc.Col(
                    (
                        dbc.Button(
                            "Open provider page",
                            href=str(model_page_url),
                            target="_blank",
                            external_link=True,
                            color="primary",
                            outline=True,
                            size="sm",
                        )
                        if isinstance(model_page_url, str) and model_page_url
                        else html.Div()
                    ),
                    width="auto",
                ),
            ],
            align="center",
            className="mb-3",
        )

        header = html.Div(header, className="mb-3")

        def _row(label: str, value: Any) -> html.Tr:
            return html.Tr([html.Td(label, className="text-muted"), html.Td(value)])

        created_cell: Any
        created_day = str(created_iso) if created_iso is not None else ""
        if created_day and len(created_day) == 10:
            created_cell = monospace(created_day)
        else:
            created_cell = html.Span("—", className="text-muted")

        pricing_in_cell = (
            monospace(pricing_in) if pricing_in else html.Span("—", className="text-muted")
        )
        pricing_out_cell = (
            monospace(pricing_out) if pricing_out else html.Span("—", className="text-muted")
        )

        body_children: list[Any] = [
            html.Div("Overview", className="text-muted small"),
            dbc.Table(
                html.Tbody(
                    [
                        _row("Model", monospace(model_id)),
                        _row("Provider", monospace(provider or "—")),
                        _row("Sub-provider", monospace(owned_by or "—")),
                        _row("Modality", monospace(modality or "—")),
                        _row("Created", created_cell),
                    ]
                ),
                bordered=False,
                striped=True,
                size="sm",
                className="table-dark mt-2",
            ),
            html.Hr(),
            html.Div("Context", className="text-muted small"),
            dbc.Table(
                html.Tbody(
                    [
                        _row("Context length", monospace(context_length or "—")),
                        _row("Max output", monospace(max_output_tokens or "—")),
                    ]
                ),
                bordered=False,
                striped=True,
                size="sm",
                className="table-dark mt-2",
            ),
            html.Hr(),
            html.Div("Pricing", className="text-muted small"),
            dbc.Table(
                html.Tbody(
                    [
                        _row("$/M input", pricing_in_cell),
                        _row("$/M output", pricing_out_cell),
                    ]
                ),
                bordered=False,
                striped=True,
                size="sm",
                className="table-dark mt-2",
            ),
            html.Hr(),
            html.Div("Description", className="text-muted small"),
            html.Div(
                str(description_full)
                if isinstance(description_full, str) and description_full
                else "—",
                className="mt-2",
                style={"whiteSpace": "pre-wrap"},
            ),
            html.Hr(),
            html.Details(
                [
                    html.Summary(
                        "Raw JSON",
                        style={"cursor": "pointer"},
                        className="text-muted small",
                    ),
                    html.Pre(
                        raw_json_preview,
                        className="mt-2",
                        style={
                            "whiteSpace": "pre-wrap",
                            "fontFamily": ("ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"),
                            "fontSize": "0.8rem",
                            "maxHeight": "40vh",
                            "overflow": "auto",
                            "backgroundColor": "rgba(255,255,255,0.06)",
                            "padding": "10px",
                            "borderRadius": "6px",
                        },
                    ),
                ],
                className="mt-2",
            ),
        ]

        body = dbc.Card(
            dbc.CardBody(body_children),
            className="bg-dark text-white",
        )

        return header, body
