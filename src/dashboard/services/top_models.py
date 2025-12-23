from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import html

from src.dashboard.components.ui import empty_state, monospace
from src.dashboard.data_sources import (
    fetch_top_models,
    filter_top_models,
    top_models_meta_rows,
    top_models_provider_options,
    top_models_source_label,
    top_models_suggested_aliases,
)


@dataclass(frozen=True)
class TopModelsView:
    content: Any
    provider_options: list[dict[str, str]]
    status: Any
    meta: Any
    aliases: Any


async def build_top_models_view(
    *,
    cfg: Any,
    provider_value: str | None,
    limit_value: int | None,
    search_value: str | None,
    force_refresh: bool,
) -> TopModelsView:
    provider = provider_value.strip() if provider_value else None
    limit = int(limit_value) if isinstance(limit_value, int) else 10

    payload = await fetch_top_models(cfg=cfg, limit=limit, refresh=force_refresh, provider=None)

    provider_options = top_models_provider_options(payload)

    status = html.Div(
        [
            html.Div(top_models_source_label(payload), className="text-muted small"),
            html.Div(
                [
                    html.Span("Updated "),
                    monospace(str(payload.get("last_updated") or "")),
                ],
                className="text-muted small",
            ),
        ]
    )

    meta_tbl = dbc.Table(
        [
            html.Tbody(
                [
                    html.Tr([html.Td(monospace(k)), html.Td(monospace(v))])
                    for k, v in top_models_meta_rows(payload)
                ]
                or [
                    html.Tr(
                        [
                            html.Td(
                                "No metadata",
                                colSpan=2,
                                className="text-center text-muted",
                            )
                        ]
                    )
                ]
            )
        ],
        striped=True,
        borderless=True,
        size="sm",
        responsive=True,
        className="table-dark",
    )

    aliases = top_models_suggested_aliases(payload)
    aliases_tbl = dbc.Table(
        [
            html.Thead(html.Tr([html.Th("Alias"), html.Th("Maps To")])),
            html.Tbody(
                [
                    html.Tr([html.Td(monospace(k)), html.Td(monospace(v))])
                    for k, v in sorted(aliases.items())
                ]
                or [
                    html.Tr(
                        [
                            html.Td(
                                "No suggested aliases",
                                colSpan=2,
                                className="text-center text-muted",
                            )
                        ]
                    )
                ]
            ),
        ],
        striped=True,
        borderless=True,
        size="sm",
        responsive=True,
        className="table-dark",
    )

    models = payload.get("models", [])
    models = models if isinstance(models, list) else []
    models = [m for m in models if isinstance(m, dict)]

    filtered = filter_top_models(
        models,
        provider=provider,
        query=search_value or "",
    )

    if not filtered:
        content = empty_state("No models found", "🔍")
    else:
        from src.dashboard.components.ag_grid import top_models_ag_grid

        content = top_models_ag_grid(filtered, grid_id="vdm-top-models-grid")

    return TopModelsView(
        content=content,
        provider_options=provider_options,
        status=status,
        meta=meta_tbl,
        aliases=aliases_tbl,
    )
