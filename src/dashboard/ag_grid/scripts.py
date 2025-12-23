"""JavaScript AG Grid cell renderers, utilities, and helpers.

This module loads the JS code from asset files and provides it to dash-ag-grid
via clientside callbacks. The JavaScript code is split across three files:
- vdm-grid-renderers.js: Cell renderer functions
- vdm-grid-helpers.js: Utility functions (copy, toast, etc.)
- vdm-grid-init.js: Initialization and registration

Key exports:
- CELL_RENDERER_SCRIPTS: the main JS string (concatenated from files)
- get_ag_grid_clientside_callback(): maps grid IDs to the JS script
"""

from __future__ import annotations

from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"
_AG_GRID_DIR = _ASSETS_DIR / "ag_grid"


def _load_js_file(filename: str) -> str:
    """Load a JavaScript file from assets/ag_grid/.

    Args:
        filename: Name of the JavaScript file to load.

    Returns:
        The file contents as a string.
    """
    path = _AG_GRID_DIR / filename
    return path.read_text(encoding="utf-8")


# Concatenate all JS files for dash-ag-grid clientside callback.
# The order matters: renderers → helpers → init
CELL_RENDERER_SCRIPTS = "\n".join(
    [
        _load_js_file("vdm-grid-renderers.js"),
        _load_js_file("vdm-grid-helpers.js"),
        _load_js_file("vdm-grid-init.js"),
    ]
)


def get_ag_grid_clientside_callback() -> dict[str, dict[str, str]]:
    """Return the clientside callback for AG-Grid cell renderers.

    Note: the keys must match the Dash component id(s) of the AgGrid instances.
    """
    return {
        "vdm-models-grid": {"javascript": CELL_RENDERER_SCRIPTS},
        "vdm-top-models-grid": {"javascript": CELL_RENDERER_SCRIPTS},
        "vdm-logs-errors-grid": {"javascript": CELL_RENDERER_SCRIPTS},
        "vdm-logs-traces-grid": {"javascript": CELL_RENDERER_SCRIPTS},
    }
