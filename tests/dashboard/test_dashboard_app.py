from __future__ import annotations

from src.dashboard.app import create_dashboard
from src.dashboard.data_sources import DashboardConfig


def test_create_dashboard_smoke() -> None:
    app = create_dashboard(cfg=DashboardConfig(api_base_url="http://localhost:8082"))
    assert app is not None
    # Basic property checks
    assert app.title == "Vandamme Dashboard"
