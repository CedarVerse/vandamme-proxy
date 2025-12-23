"""Shared AG Grid factory functions to reduce repeated configuration boilerplate."""

from typing import Any

import dash_ag_grid as dag  # type: ignore[import-untyped]

# Common CSS applied to all grid instances
_DEFAULT_GRID_CSS = {
    "height": "70vh",
    "width": "100%",
    "minHeight": "500px",
}

# Common default column definitions
_DEFAULT_COLUMN_DEF = {
    "sortable": True,
    "resizable": True,
    "filter": True,
}

# Base dashGridOptions shared across all grids
_BASE_DASH_GRID_OPTIONS = {
    "animateRows": True,
    "rowSelection": {"mode": "multiRow"},
    "suppressDragLeaveHidesColumns": True,
    "pagination": True,
    "paginationPageSize": 50,
    "paginationPageSizeSelector": [25, 50, 100, 200],
    "domLayout": "normal",
    "suppressContextMenu": False,
    "enableCellTextSelection": True,
    "ensureDomOrder": True,
    "localeText": {
        "page": "Page",
        "to": "to",
        "of": "of",
        "first": "First",
        "last": "Last",
        "next": "Next",
        "previous": "Previous",
        "loadingOoo": "Loading...",
        "filterOoo": "Filter...",
    },
}


def build_ag_grid(
    *,
    grid_id: str,
    column_defs: list[dict[str, Any]],
    row_data: list[dict[str, Any]],
    custom_css: dict[str, Any] | None = None,
    no_rows_message: str | None = None,
) -> dag.AgGrid:
    """Build an AG-Grid component with standard dark theme and options.

    This factory reduces boilerplate by providing common defaults that apply
    across all dashboard grids.

    Args:
        grid_id: Unique ID for the grid component
        column_defs: Column definitions for this specific grid
        row_data: Row data to display
        custom_css: Optional CSS overrides (defaults to standard 70vh height)
        no_rows_message: Optional override for the "no rows" text
    """
    options: dict[str, Any] = dict(_BASE_DASH_GRID_OPTIONS)
    if no_rows_message:
        base_locale_text: dict[str, str] = dict(options["localeText"])  # type: ignore[assignment]
        base_locale_text["noRowsToShow"] = no_rows_message
        options["localeText"] = base_locale_text

    return dag.AgGrid(
        id=grid_id,
        className="ag-theme-alpine-dark",
        style=custom_css or _DEFAULT_GRID_CSS,
        columnDefs=column_defs,
        rowData=row_data,
        defaultColDef=_DEFAULT_COLUMN_DEF,
        dashGridOptions=options,
        dangerously_allow_code=True,
    )
