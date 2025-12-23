from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import html

from src.dashboard.components.ui import monospace, provider_badge, status_badge


def providers_table(health: dict[str, Any]) -> dbc.Table:
    providers = health.get("providers")
    if not isinstance(providers, dict):
        providers = {}

    default_provider = health.get("default_provider")
    if not isinstance(default_provider, str):
        default_provider = ""

    header = html.Thead(
        html.Tr(
            [
                html.Th("Provider"),
                html.Th("Format"),
                html.Th("Base URL"),
                html.Th("API key (sha256)"),
            ]
        )
    )

    body_rows = []
    for provider_name in sorted(providers.keys()):
        pdata = providers.get(provider_name)
        if not isinstance(pdata, dict):
            continue
        api_format = pdata.get("api_format", "unknown")
        base_url = pdata.get("base_url")
        api_key_hash = pdata.get("api_key_hash", "<not set>")

        is_default = bool(default_provider) and provider_name == default_provider

        provider_cell = [provider_badge(provider_name)]
        if is_default:
            provider_cell.append(
                dbc.Badge(
                    "default",
                    color="info",
                    pill=True,
                    className="ms-1",
                )
            )

        # api_key_hash is already in the same format we log (sha256:<8>)
        key_text = str(api_key_hash)
        key_missing = key_text == "<not set>"

        body_rows.append(
            html.Tr(
                [
                    html.Td(provider_cell),
                    html.Td(monospace(api_format)),
                    html.Td(monospace(base_url or "—")),
                    html.Td(
                        monospace(key_text)
                        if not key_missing
                        else html.Span("<not set>", className="text-muted")
                    ),
                ],
                className="table-active" if is_default else None,
            )
        )

    return dbc.Table(
        [header, html.Tbody(body_rows)],
        bordered=False,
        hover=True,
        responsive=True,
        striped=True,
        size="sm",
    )


def health_banner(health: dict[str, Any]) -> dbc.Alert:
    status = str(health.get("status", "unknown"))
    ts = str(health.get("timestamp", ""))

    color = (
        "success"
        if status.lower() == "healthy"
        else "warning"
        if status.lower() == "degraded"
        else "secondary"
    )

    details = [
        html.Div(
            [
                status_badge(status=status),
                html.Span(" "),
                html.Span("System status"),
                html.Span(" · ", className="text-muted"),
                html.Span("Updated "),
                monospace(ts),
            ]
        )
    ]

    suggestions = health.get("suggestions")
    if isinstance(suggestions, list) and suggestions:
        details.append(html.Div(html.Hr()))
        details.append(html.Div("Suggestions", className="text-muted small"))
        details.append(html.Div(html.Ul([html.Li(str(s)) for s in suggestions])))

    return dbc.Alert(details, color=color, className="mb-0")
