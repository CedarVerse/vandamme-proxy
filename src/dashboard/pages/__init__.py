"""Dashboard page layouts.

This package contains layout factories for the Dash dashboard pages.

Important naming note:
- `src.dashboard.pages` is a *package* of page layout factories.

All call sites should import from this package (or specific page modules).
"""

from __future__ import annotations

from src.dashboard.components.metrics import kpis_grid, metrics_disabled_callout
from src.dashboard.components.overview import health_banner, providers_table

# Re-export layout factories directly from their new per-page modules.
#
# We intentionally do NOT try to import `src.dashboard.pages.py` here, because the
# package name `src.dashboard.pages` now resolves to this directory.
from src.dashboard.pages.aliases import aliases_layout
from src.dashboard.pages.logs import logs_layout
from src.dashboard.pages.metrics import (
    compute_metrics_views,
    metrics_layout,
    parse_totals_for_chart,
    token_composition_chart,
)
from src.dashboard.pages.models import models_layout
from src.dashboard.pages.overview import overview_layout
from src.dashboard.pages.token_counter import token_counter_layout
from src.dashboard.pages.top_models import top_models_layout

__all__ = [
    "aliases_layout",
    "compute_metrics_views",
    "health_banner",
    "kpis_grid",
    "logs_layout",
    "metrics_disabled_callout",
    "metrics_layout",
    "models_layout",
    "overview_layout",
    "parse_totals_for_chart",
    "providers_table",
    "token_composition_chart",
    "top_models_layout",
    "token_counter_layout",
]
