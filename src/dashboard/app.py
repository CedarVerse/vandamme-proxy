from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import dash
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import Input, Output, dcc, html

from src.dashboard.callbacks.aliases import register_aliases_callbacks
from src.dashboard.callbacks.clientside import register_clientside_callbacks
from src.dashboard.callbacks.logs import register_logs_callbacks
from src.dashboard.callbacks.metrics import register_metrics_callbacks
from src.dashboard.callbacks.models import register_models_callbacks
from src.dashboard.callbacks.overview import register_overview_callbacks
from src.dashboard.callbacks.theme import register_theme_callbacks
from src.dashboard.callbacks.token_counter import register_token_counter_callbacks
from src.dashboard.callbacks.top_models import register_top_models_callbacks
from src.dashboard.data_sources import DashboardConfigProtocol
from src.dashboard.routing import render_page_for_path

logger = logging.getLogger(__name__)

# NOTE: AG-Grid JS helpers are imported inside create_dashboard when building index_string.
# Keeping this import out of module scope avoids scoping pitfalls.


def _run(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Dash callbacks are sync; when we are already in an event loop (rare in prod),
        # run in a new loop.
        return asyncio.run(coro)

    return asyncio.run(coro)


def create_dashboard(*, cfg: DashboardConfigProtocol) -> dash.Dash:
    app = dash.Dash(
        __name__,
        requests_pathname_prefix="/dashboard/",
        assets_folder=str(Path(__file__).resolve().parents[2] / "assets"),
        assets_url_path="assets",
        external_stylesheets=[dbc.themes.DARKLY],
        suppress_callback_exceptions=True,
        title="Vandamme Dashboard",
    )

    app.layout = html.Div(
        [
            dcc.Location(id="vdm-url"),
            dcc.Store(id="vdm-theme-store", data={"theme": "dark"}),
            dbc.Navbar(
                dbc.Container(
                    [
                        html.Div(
                            [
                                dbc.NavbarBrand(
                                    html.A(
                                        html.Img(
                                            src=app.get_asset_url("vandamme-93x64px.png"),
                                            alt="Vandamme Dashboard",
                                            className="vdm-navbar-logo",
                                        ),
                                        href="/dashboard/",
                                        className="d-flex align-items-center",
                                        title="Vandamme",
                                    ),
                                    href="/dashboard/",
                                ),
                                dbc.Nav(
                                    [
                                        dbc.NavLink("Overview", href="/dashboard/", active="exact"),
                                        dbc.NavLink(
                                            "Metrics", href="/dashboard/metrics", active="exact"
                                        ),
                                        dbc.NavLink(
                                            "Models", href="/dashboard/models", active="exact"
                                        ),
                                        dbc.NavLink(
                                            "Top Models",
                                            href="/dashboard/top-models",
                                            active="exact",
                                        ),
                                        dbc.NavLink(
                                            "Aliases", href="/dashboard/aliases", active="exact"
                                        ),
                                        dbc.NavLink(
                                            "Token Counter",
                                            href="/dashboard/token-counter",
                                            active="exact",
                                        ),
                                        dbc.NavLink("Logs", href="/dashboard/logs", active="exact"),
                                    ],
                                    pills=True,
                                ),
                                dbc.Nav(
                                    [
                                        dbc.NavLink(
                                            "API Docs",
                                            href="/docs",
                                            target="_blank",
                                            external_link=True,
                                        ),
                                    ],
                                    pills=True,
                                ),
                            ],
                            className="d-flex align-items-center gap-2 ps-2",
                        ),
                        html.Span(id="vdm-global-error", className="text-danger ms-auto"),
                    ],
                    fluid=True,
                    className="px-0",
                ),
                color="dark",
                dark=True,
                className="mb-0",
            ),
            html.Div(id="vdm-page"),
        ]
    )

    @app.callback(Output("vdm-page", "children"), Input("vdm-url", "pathname"))
    def route(pathname: str | None) -> Any:
        return render_page_for_path(pathname)

    # Inject AG Grid renderer scripts as external files.
    # Scripts are loaded in dependency order (renderers → helpers → init).
    # The scripts are also loaded via dash-ag-grid's clientside callback API.
    scripts_html = "\n".join(
        [
            '<script src="/dashboard/assets/ag_grid/vdm-grid-renderers.js"></script>',
            '<script src="/dashboard/assets/ag_grid/vdm-grid-helpers.js"></script>',
            '<script src="/dashboard/assets/ag_grid/vdm-grid-init.js"></script>',
        ]
    )
    app.index_string = app.index_string.replace("</body>", f"{scripts_html}</body>")

    # Register callback modules (keeps app.py focused on wiring).
    register_clientside_callbacks(app=app)
    register_overview_callbacks(app=app, cfg=cfg, run=_run)
    register_theme_callbacks(app=app)
    register_metrics_callbacks(app=app, cfg=cfg, run=_run)
    register_models_callbacks(app=app, cfg=cfg, run=_run)
    register_top_models_callbacks(app=app, cfg=cfg, run=_run)
    register_aliases_callbacks(app=app, cfg=cfg, run=_run)
    register_logs_callbacks(app=app, cfg=cfg, run=_run)
    register_token_counter_callbacks(app=app, cfg=cfg, run=_run)

    # Dashboard callbacks are registered in dedicated modules under `src.dashboard.callbacks`.

    return app
