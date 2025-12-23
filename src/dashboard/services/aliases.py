from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import html

from src.dashboard.components.ui import alias_table, empty_state, monospace, provider_badge
from src.dashboard.data_sources import fetch_aliases


@dataclass(frozen=True)
class AliasesView:
    content: Any


async def build_aliases_view(*, cfg: Any, search_term: str | None) -> AliasesView:
    aliases_data = await fetch_aliases(cfg=cfg)
    aliases = aliases_data.get("aliases", {})

    # Filter aliases based on search term
    if search_term and search_term.strip():
        search_lower = search_term.lower().strip()
        filtered_aliases: dict[str, dict[str, str]] = {}
        for provider, provider_aliases in aliases.items():
            if not isinstance(provider_aliases, dict):
                continue

            filtered = {
                alias: mapping
                for alias, mapping in provider_aliases.items()
                if search_lower in alias.lower() or search_lower in mapping.lower()
            }
            if filtered:
                filtered_aliases[provider] = filtered

        aliases = filtered_aliases

    if not aliases:
        return AliasesView(content=empty_state("No aliases found matching your criteria", "🔍"))

    sections: list[dbc.AccordionItem] = []
    for provider, provider_aliases in aliases.items():
        if not isinstance(provider_aliases, dict):
            continue

        rows = [
            html.Tr([html.Td(alias_name), html.Td(monospace(maps_to))])
            for alias_name, maps_to in provider_aliases.items()
        ]
        if not rows:
            continue

        sections.append(
            dbc.AccordionItem(
                [
                    html.H5([provider_badge(provider), f" {provider}"]),
                    alias_table({provider: provider_aliases}),
                ],
                title=f"{provider} ({len(rows)} aliases)",
                item_id=provider,
            )
        )

    if not sections:
        return AliasesView(content=empty_state("No aliases configured", "📋"))

    return AliasesView(content=dbc.Accordion(sections, start_collapsed=True, flush=True))
