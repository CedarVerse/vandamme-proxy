from __future__ import annotations

from src.dashboard.app import create_dashboard
from src.dashboard.data_sources import DashboardConfig


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
