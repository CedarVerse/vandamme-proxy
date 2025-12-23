from __future__ import annotations

from pathlib import Path

from src.dashboard.app import create_dashboard
from src.dashboard.data_sources import DashboardConfig


def test_ag_grid_asset_files_exist() -> None:
    """Verify that AG Grid JavaScript asset files exist and contain expected content."""
    assets_dir = Path(__file__).resolve().parents[2] / "assets" / "ag_grid"

    # Check that all three script files exist
    renderers_js = assets_dir / "vdm-grid-renderers.js"
    helpers_js = assets_dir / "vdm-grid-helpers.js"
    init_js = assets_dir / "vdm-grid-init.js"

    assert renderers_js.exists(), "vdm-grid-renderers.js should exist"
    assert helpers_js.exists(), "vdm-grid-helpers.js should exist"
    assert init_js.exists(), "vdm-grid-init.js should exist"

    # Verify renderers file contains the renderer functions
    renderers_content = renderers_js.read_text(encoding="utf-8")
    assert "window.vdmModelPageLinkRenderer" in renderers_content
    assert "window.vdmModelIdWithIconRenderer" in renderers_content
    assert "window.vdmProviderBadgeRenderer" in renderers_content
    assert "window.vdmFormattedNumberRenderer" in renderers_content

    # Verify helpers file contains utility functions
    helpers_content = helpers_js.read_text(encoding="utf-8")
    assert "window.vdmCopyText" in helpers_content
    assert "window.vdmCopySelectedModelIds" in helpers_content
    assert "window.vdmDateComparator" in helpers_content
    assert "window.escapeHtml" in helpers_content

    # Verify init file contains registration logic
    init_content = init_js.read_text(encoding="utf-8")
    assert "window.dashAgGridFunctions" in init_content
    assert "window.dashAgGridComponentFunctions" in init_content
    assert "vdmToast" in init_content
    assert "vdmAttachModelCellCopyListener" in init_content


def test_ag_grid_clientside_callback_returns_empty_string() -> None:
    """Verify that the clientside callback returns empty strings (scripts loaded externally)."""
    from src.dashboard.ag_grid.scripts import get_ag_grid_clientside_callback

    callbacks = get_ag_grid_clientside_callback()

    # All callbacks should return empty javascript strings
    for grid_id, config in callbacks.items():
        assert "javascript" in config, f"{grid_id} should have 'javascript' key"
        assert config["javascript"] == "", f"{grid_id} should have empty javascript string"

    # Verify expected grid IDs are present
    assert "vdm-models-grid" in callbacks
    assert "vdm-top-models-grid" in callbacks
    assert "vdm-logs-errors-grid" in callbacks
    assert "vdm-logs-traces-grid" in callbacks


def test_create_dashboard_smoke() -> None:
    app = create_dashboard(cfg=DashboardConfig(api_base_url="http://localhost:8082"))
    assert app is not None
    # Basic property checks
    assert app.title == "Vandamme Dashboard"


def test_models_detail_drawer_ids_exist() -> None:
    """Smoke-check that models layout includes the detail drawer + store IDs."""

    # Dash callback functions are wrapped; calling them directly requires extra
    # callback context that is not available in unit tests. Instead, import the
    # layout factory and inspect the component tree.
    from src.dashboard.pages import models_layout

    page = models_layout()

    def _collect_ids(node):  # noqa: ANN001
        out = set()
        if node is None:
            return out
        if isinstance(node, (list, tuple)):
            for c in node:
                out |= _collect_ids(c)
            return out
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            out.add(node_id)
        children = getattr(node, "children", None)
        out |= _collect_ids(children)
        return out

    ids = _collect_ids(page)

    assert "vdm-models-detail-store" in ids
    assert "vdm-model-details-drawer" in ids
    assert "vdm-model-details-header" in ids
    assert "vdm-model-details-body" in ids
    assert "vdm-model-details-close" in ids

    # Raw JSON is rendered inside the drawer body; presence is validated by render smoke.
