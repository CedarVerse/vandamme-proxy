from __future__ import annotations

import dash
from dash import Input, Output


def register_theme_callbacks(*, app: dash.Dash) -> None:
    @app.callback(
        Output("vdm-theme-store", "data"),
        Input("vdm-theme-toggle", "value"),
        prevent_initial_call=True,
    )
    def set_theme(is_dark: bool) -> dict[str, str]:
        return {"theme": "dark" if is_dark else "light"}
