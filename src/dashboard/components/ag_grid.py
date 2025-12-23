"""AG-Grid component for the dashboard with dark theme support."""

from typing import Any

import dash_ag_grid as dag  # type: ignore[import-untyped]

from src.dashboard.ag_grid.factories import build_ag_grid
from src.dashboard.ag_grid.scripts import (
    get_ag_grid_clientside_callback as _get_ag_grid_clientside_callback,
)
from src.dashboard.ag_grid.transformers import (
    logs_errors_row_data,
    logs_traces_row_data,
    models_row_data,
    top_models_row_data,
)


def top_models_ag_grid(
    models: list[dict[str, Any]],
    *,
    grid_id: str = "vdm-top-models-grid",
) -> dag.AgGrid:
    """Create an AG-Grid table for Top Models.

    Expects rows shaped like the `/top-models` API output items.
    """
    column_defs = [
        {
            "headerName": "Provider",
            "field": "provider",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 130,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Sub-provider",
            "field": "sub_provider",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 160,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Model ID",
            "field": "id",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 2,
            "minWidth": 260,
            "cellStyle": {"cursor": "copy"},
        },
        {
            "headerName": "Name",
            "field": "name",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 160,
        },
        {
            "headerName": "Context",
            "field": "context_window",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 120,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Avg $/M",
            "field": "avg_per_million",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 120,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Caps",
            "field": "capabilities",
            "sortable": False,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 220,
        },
    ]

    return build_ag_grid(
        grid_id=grid_id,
        column_defs=column_defs,
        row_data=top_models_row_data(models),
        no_rows_message="No models found",
    )


# --- Models AG Grid ---


def models_ag_grid(
    models: list[dict[str, Any]],
    grid_id: str = "vdm-models-grid",
) -> dag.AgGrid:
    """Create an AG-Grid table for models with dark theme and advanced features.

    Args:
        models: List of model dictionaries
        grid_id: Unique ID for the grid component

    Returns:
        AG-Grid component with models data
    """
    row_data = models_row_data(models)

    # Define column definitions with new order: Created → Actions → Model ID → metadata
    column_defs = [
        {
            "headerName": "Created",
            "field": "created_iso",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 120,  # Fixed width for yyyy-mm-dd format (plus padding)
            "suppressSizeToFit": True,
            "suppressMovable": False,
            "sort": "desc",  # Default sort by creation date (newest first)
            "tooltipField": "created_relative",
            "comparator": {"function": "vdmDateComparator"},
        },
        {
            "headerName": "Actions",
            "field": "actions",
            "sortable": False,
            "filter": False,
            "resizable": False,
            "width": 80,  # Fixed width for emoji icon with padding
            "suppressSizeToFit": True,
            "suppressMovable": True,
            "cellRenderer": "vdmModelPageLinkRenderer",
        },
        {
            "headerName": "Sub-Provider",
            "field": "owned_by",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 140,
        },
        {
            "headerName": "Model ID",
            "field": "id",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 2,
            "minWidth": 220,
            "suppressMovable": False,
            "cellStyle": {"cursor": "copy"},
            "tooltipField": "description_full",
            "cellRenderer": "vdmModelIdWithIconRenderer",
        },
        {
            "headerName": "Modality",
            "field": "architecture_modality",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 170,
        },
        {
            "headerName": "Context",
            "field": "context_length",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Max out",
            "field": "max_output_tokens",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "$/M in",
            "field": "pricing_prompt_per_million",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "$/M out",
            "field": "pricing_completion_per_million",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Description",
            "field": "description_preview",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 3,
            "minWidth": 360,
            "tooltipField": "description_full",
        },
    ]

    return build_ag_grid(
        grid_id=grid_id,
        column_defs=column_defs,
        row_data=row_data,
        no_rows_message="No models found",
        dash_grid_options_overrides={
            "rowSelection": {"enableClickSelection": True},
        },
    )


def logs_errors_ag_grid(
    errors: list[dict[str, Any]],
    grid_id: str = "vdm-logs-errors-grid",
) -> dag.AgGrid:
    """Create an AG-Grid table for error logs with dark theme and provider badges.

    Args:
        errors: List of error log dictionaries
        grid_id: Unique ID for the grid component

    Returns:
        AG-Grid component with error logs data
    """
    row_data = logs_errors_row_data(errors)

    # Define column definitions for errors
    column_defs = [
        {
            "headerName": "Time",
            "field": "time_formatted",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
            "tooltipField": "time_relative",
            "sort": "desc",  # Default sort by time (newest first)
        },
        {
            "headerName": "Provider",
            "field": "provider",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 130,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmProviderBadgeRenderer",
        },
        {
            "headerName": "Model",
            "field": "model",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 200,
            "cellStyle": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"},
        },
        {
            "headerName": "Error Type",
            "field": "error_type",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 160,
            "suppressSizeToFit": True,
        },
        {
            "headerName": "Error Message",
            "field": "error",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 3,
            "minWidth": 300,
            "cellStyle": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"},
            "tooltipField": "error",
        },
    ]

    return build_ag_grid(
        grid_id=grid_id,
        column_defs=column_defs,
        row_data=row_data,
        no_rows_message="No errors found",
    )


def logs_traces_ag_grid(
    traces: list[dict[str, Any]],
    grid_id: str = "vdm-logs-traces-grid",
) -> dag.AgGrid:
    """Create an AG-Grid table for trace logs with dark theme and provider badges.

    Args:
        traces: List of trace log dictionaries
        grid_id: Unique ID for the grid component

    Returns:
        AG-Grid component with trace logs data
    """
    row_data = logs_traces_row_data(traces)

    # Define column definitions for traces
    column_defs = [
        {
            "headerName": "Time",
            "field": "time_formatted",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
            "tooltipField": "time_relative",
            "sort": "desc",  # Default sort by time (newest first)
        },
        {
            "headerName": "Provider",
            "field": "provider",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 130,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmProviderBadgeRenderer",
        },
        {
            "headerName": "Model",
            "field": "model",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 200,
            "cellStyle": {"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"},
        },
        {
            "headerName": "Status",
            "field": "status",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmStatusBadgeRenderer",
        },
        {
            "headerName": "Duration",
            "field": "duration_formatted",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 100,
            "suppressSizeToFit": True,
            "tooltipField": "duration_ms",
            "comparator": {"function": "vdmNumericComparator"},
        },
        {
            "headerName": "In Tokens",
            "field": "input_tokens_raw",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmFormattedNumberRenderer",
        },
        {
            "headerName": "Out Tokens",
            "field": "output_tokens_raw",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmFormattedNumberRenderer",
        },
        {
            "headerName": "Cache Read",
            "field": "cache_read_tokens_raw",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmFormattedNumberRenderer",
        },
        {
            "headerName": "Cache Create",
            "field": "cache_creation_tokens_raw",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "width": 110,
            "suppressSizeToFit": True,
            "cellRenderer": "vdmFormattedNumberRenderer",
        },
    ]

    return build_ag_grid(
        grid_id=grid_id,
        column_defs=column_defs,
        row_data=row_data,
        no_rows_message="No traces found",
    )


def get_ag_grid_clientside_callback() -> dict[str, dict[str, str]]:
    """Return the clientside callback for AG-Grid cell renderers.

    Note: the keys must match the Dash component id(s) of the AgGrid instances.
    Delegates to the scripts module.
    """
    return _get_ag_grid_clientside_callback()
