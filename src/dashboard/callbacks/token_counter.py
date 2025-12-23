from __future__ import annotations

from typing import Any

import dash
from dash import Input, Output, html

from src.dashboard.components.ui import token_display
from src.dashboard.data_sources import DashboardConfigProtocol


def register_token_counter_callbacks(
    *,
    app: dash.Dash,
    cfg: DashboardConfigProtocol,
    run: Any,
) -> None:
    @app.callback(
        Output("vdm-token-counter-model", "options"),
        Input("vdm-url", "pathname"),
        prevent_initial_call=False,
    )
    def load_token_counter_models(_pathname: str) -> list[dict[str, Any]]:
        from src.dashboard.services.token_counter import (
            TokenCounterModelsView,
            build_token_counter_model_options,
        )

        view: TokenCounterModelsView = run(build_token_counter_model_options(cfg=cfg))
        return view.as_options()

    @app.callback(
        Output("vdm-token-counter-result", "children"),
        Input("vdm-token-counter-message", "value"),
        Input("vdm-token-counter-system", "value"),
        Input("vdm-token-counter-model", "value"),
        prevent_initial_call=False,
    )
    def count_tokens(
        message: str | None,
        system_message: str | None,
        model: str | None,
    ) -> Any:
        if not message and not system_message:
            return html.Div("Enter a message to count tokens", className="text-muted small")

        if not model:
            return html.Div("Select a model to count tokens", className="text-warning small")

        total_chars = len(message or "") + len(system_message or "")
        estimated_tokens = max(1, total_chars // 4)

        return token_display(estimated_tokens, "Estimated Tokens")

    @app.callback(
        Output("vdm-token-counter-message", "value"),
        Output("vdm-token-counter-system", "value"),
        Input("vdm-token-counter-clear", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_token_counter(_n_clicks: int) -> tuple[None, None]:
        return None, None
