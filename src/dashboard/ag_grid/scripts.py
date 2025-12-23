"""JavaScript AG Grid cell renderers, utilities, and helpers.

The JavaScript code is loaded from asset files under assets/ag_grid/:
- vdm-grid-renderers.js: Cell renderer functions
- vdm-grid-helpers.js: Utility functions (copy, toast, etc.)
- vdm-grid-init.js: Initialization and registration

These scripts are loaded via Dash's built-in asset loading (external <script>
tags). The clientside callback below returns minimal configuration since
dash-ag-grid resolves cell renderers from window.dashAgGridFunctions that
are registered by the external scripts.

Key exports:
- get_ag_grid_clientside_callback(): maps grid IDs to minimal callback config
"""

from __future__ import annotations


def get_ag_grid_clientside_callback() -> dict[str, dict[str, str]]:
    """Return the clientside callback configuration for AG-Grid cell renderers.

    The JavaScript code is loaded via external script tags in app.py, so this
    returns an empty javascript string. The cell renderers are registered on
    window.dashAgGridFunctions by the external scripts.

    Note: the keys must match the Dash component id(s) of the AgGrid instances.
    """
    return {
        "vdm-models-grid": {"javascript": ""},
        "vdm-top-models-grid": {"javascript": ""},
        "vdm-logs-errors-grid": {"javascript": ""},
        "vdm-logs-traces-grid": {"javascript": ""},
    }
