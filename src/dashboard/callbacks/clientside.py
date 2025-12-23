from __future__ import annotations

import dash
from dash import Input, Output


def register_clientside_callbacks(*, app: dash.Dash) -> None:
    # Simple no-op clientside callback placeholder (keeps dash happy, avoids attribute errors)
    app.clientside_callback(
        "function(pathname){return pathname;}",
        Output("vdm-models-grid", "id"),
        Input("vdm-url", "pathname"),
        prevent_initial_call=True,
    )

    # No-op callbacks for logs grids (prevents grid recreation on updates)
    app.clientside_callback(
        "function(){return arguments[0];}",
        Output("vdm-logs-errors-grid", "id"),
        Input("vdm-logs-poll", "n_intervals"),
        prevent_initial_call=True,
    )
    app.clientside_callback(
        "function(){return arguments[0];}",
        Output("vdm-logs-traces-grid", "id"),
        Input("vdm-logs-poll", "n_intervals"),
        prevent_initial_call=True,
    )

    # Single toast renderer for BOTH:
    # - "Copy selected IDs" button
    # - click-to-copy on Model ID cells
    app.clientside_callback(
        """
        async function(copy_clicks, toast_clicks) {
            // If the user clicked the "Copy selected IDs" button, perform copy-selected.
            if (copy_clicks) {
                try {
                    const r = await window.vdmCopySelectedModelIds('vdm-models-grid');
                    const ok = r && r.ok;
                    const msg = (r && r.message) ? r.message : 'Copy failed';
                    return [
                        true,
                        msg,
                        ok ? 'success' : 'warning',
                        copy_clicks,
                        dash_clientside.no_update,
                    ];
                } catch (e) {
                    const msg = 'Copy failed: ' + (e && e.message ? e.message : String(e));
                    return [
                        true,
                        msg,
                        'danger',
                        copy_clicks,
                        dash_clientside.no_update,
                    ];
                }
            }

            // If grid JS triggered a toast click, render its payload.
            if (toast_clicks) {
                const payload = window.__vdm_last_toast_payload;
                if (payload) {
                    let obj;
                    try {
                        obj = JSON.parse(payload);
                    } catch (e) {
                        obj = { level: 'info', message: String(payload) };
                    }

                    const modelId = obj && obj.model_id;
                    if (modelId && !obj.message) {
                        obj.message = 'Copied model id: ' + String(modelId);
                        obj.level = obj.level || 'success';
                    }

                    const level = obj.level || 'info';
                    const message = obj.message || '';
                    const icon =
                        level === 'success'
                            ? 'success'
                            : level === 'danger'
                              ? 'danger'
                              : 'warning';
                    return [
                        true,
                        message,
                        icon,
                        dash_clientside.no_update,
                        payload,
                    ];
                }
            }

            return [
                false,
                dash_clientside.no_update,
                dash_clientside.no_update,
                dash_clientside.no_update,
                dash_clientside.no_update,
            ];
        }
        """,
        Output("vdm-models-copy-toast", "is_open"),
        Output("vdm-models-copy-toast", "children"),
        Output("vdm-models-copy-toast", "icon"),
        Output("vdm-models-copy-sink", "children"),
        Output("vdm-models-toast-payload", "children"),
        Input("vdm-models-copy-ids", "n_clicks"),
        Input("vdm-models-toast-trigger", "n_clicks"),
        prevent_initial_call=True,
    )
