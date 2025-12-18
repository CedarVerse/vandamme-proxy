"""AG-Grid component for the dashboard with dark theme support."""

from typing import Any

import dash_ag_grid as dag  # type: ignore[import-untyped]

from src.dashboard.components.ui import format_model_created_timestamp, format_timestamp


def models_ag_grid(
    models: list[dict[str, Any]],
    grid_id: str = "models-grid",
) -> dag.AgGrid:
    """Create an AG-Grid table for models with dark theme and advanced features.

    Args:
        models: List of model dictionaries
        grid_id: Unique ID for the grid component

    Returns:
        AG-Grid component with models data
    """
    # Define column definitions
    column_defs = [
        {
            "headerName": "Model ID",
            "field": "id",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 2,
            "minWidth": 200,
            "suppressMovable": False,
            "sort": "asc",  # Default sort by model ID
            "cellStyle": {"cursor": "copy"},
        },
        {
            "headerName": "Created",
            # Show the canonical timestamp in the cell and keep the relative time in the tooltip.
            "field": "created_iso",
            "sortable": True,
            "filter": True,
            "resizable": True,
            "flex": 1,
            "minWidth": 150,
            "suppressMovable": False,
            # Sort uses numeric `created` from the row via the comparator.
            "tooltipField": "created_relative",
            "comparator": {"function": "vdmDateComparator"},
        },
        {
            "headerName": "Actions",
            "field": "actions",
            "sortable": False,
            "filter": False,
            "resizable": False,
            "width": 100,
            "suppressSizeToFit": True,
            "suppressMovable": True,
            "pinned": "right",
            "cellRenderer": "agGroupCellRenderer",
            "cellRendererParams": {
                "suppressCount": True,
            },
        },
    ]

    # Prepare row data for AG-Grid
    row_data = []
    for model in models:
        # Handle both millisecond and second timestamps
        created = model.get("created")
        created_value = 0 if created is None else created
        if created_value > 1e12:
            created_value = created_value / 1000

        created_iso = format_model_created_timestamp(created_value)
        created_relative = format_timestamp(created_iso)

        created_day = (created_iso or "")[:10]

        row = {
            "id": model.get("id", "Unknown"),
            "provider": model.get("provider", "multiple"),
            "created": int(created_value),
            "created_relative": created_relative or "Unknown",
            "created_iso": created_day,
        }
        row_data.append(row)

    # Custom CSS for dark theme
    # NOTE: Using a viewport-based height avoids the common "100% of an auto-height parent"
    # trap where AG-Grid renders but no rows are visible.
    custom_css = {
        "height": "70vh",
        "width": "100%",
        "minHeight": "500px",
    }

    # Create the AG-Grid component with proper parameter names
    return dag.AgGrid(
        id=grid_id,
        className="ag-theme-alpine-dark",
        style=custom_css,
        columnDefs=column_defs,
        rowData=row_data,
        defaultColDef={
            "sortable": True,
            "resizable": True,
            "filter": True,
        },
        dashGridOptions={
            "animateRows": True,
            # Community-friendly multi-row selection (AG Grid v32+ object form)
            "rowSelection": {"mode": "multiRow"},
            "suppressDragLeaveHidesColumns": True,
            "pagination": True,
            "paginationPageSize": 50,
            "paginationPageSizeSelector": [25, 50, 100, 200],
            "domLayout": "normal",
            "suppressContextMenu": False,
            "enableCellTextSelection": True,
            "ensureDomOrder": True,
            "localeText": {
                "page": "Page",
                "to": "to",
                "of": "of",
                "first": "First",
                "last": "Last",
                "next": "Next",
                "previous": "Previous",
                "loadingOoo": "Loading...",
                "noRowsToShow": "No models found",
                "filterOoo": "Filter...",
            },
        },
    )


# JavaScript functions for AG-Grid
# These will be injected into the app's HTML
CELL_RENDERER_SCRIPTS = """
console.info('[vdm] CELL_RENDERER_SCRIPTS loaded');
// Date comparator function for sorting by creation date
window.dateComparator = function(dateA, dateB) {
    if (dateA === null && dateB === null) {
        return 0;
    }
    if (dateA === null) {
        return -1;
    }
    if (dateB === null) {
        return 1;
    }
    return dateA - dateB;
};

// AG Grid comparator wrapper for the Created column to ensure numeric sort on raw created
window.vdmDateComparator = function(valueA, valueB, nodeA, nodeB) {
    const a = (nodeA && nodeA.data && nodeA.data.created) || 0;
    const b = (nodeB && nodeB.data && nodeB.data.created) || 0;
    return a - b;
};

// Format unix seconds as relative time (e.g. "2m ago")
window.formatRelativeTimestamp = function(unixSeconds) {
    if (!unixSeconds) {
        return 'Unknown';
    }

    const tsMs = unixSeconds * 1000;
    const diffMs = Date.now() - tsMs;

    // Future timestamps (clock skew)
    if (diffMs < 0) {
        return 'Just now';
    }

    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 10) return 'Just now';
    if (diffSec < 60) return diffSec + 's ago';

    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + 'm ago';

    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + 'h ago';

    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 30) return diffDay + 'd ago';

    // Fallback to a stable short date for older entries
    return new Date(tsMs).toLocaleDateString();
};

// Absolute timestamp for tooltips (local time)
window.formatAbsoluteTimestamp = function(unixSeconds) {
    if (!unixSeconds) {
        return '';
    }
    const tsMs = unixSeconds * 1000;
    const d = new Date(tsMs);

    // Match Python's isoformat-ish output used by the dashboard cards:
    // - local time
    // - explicit numeric timezone offset
    const pad = (n) => String(n).padStart(2, '0');

    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hour = pad(d.getHours());
    const minute = pad(d.getMinutes());
    const second = pad(d.getSeconds());

    const tzMin = -d.getTimezoneOffset();
    const sign = tzMin >= 0 ? '+' : '-';
    const tzAbs = Math.abs(tzMin);
    const tzH = pad(Math.floor(tzAbs / 60));
    const tzM = pad(tzAbs % 60);

    return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${tzH}:${tzM}`;
};

// AG Grid formatter wrappers: AG Grid calls these with `params`
window.vdmFormatRelativeTimestamp = function(params) {
    const rel = params && params.data && params.data.created_relative;
    return rel || window.formatRelativeTimestamp(params && params.value);
};

window.vdmFormatRelativeFromRow = function(params) {
    const rel = params && params.data && params.data.created_relative;
    return rel || window.formatRelativeTimestamp(params && params.data && params.data.created);
};

window.vdmFormatAbsoluteTimestamp = function(params) {
    const iso = params && params.data && params.data.created_iso;
    return iso ? iso : window.formatAbsoluteTimestamp(params && params.value);
};

window.vdmDateComparator = function(dateA, dateB) {
    // Compare underlying numeric created values to keep sort stable.
    return (dateA || 0) - (dateB || 0);
};


// Copy selected model IDs to clipboard (newline-separated)
window.vdmCopySelectedModelIds = async function(gridId) {
    console.debug('[vdm][copy] invoking vdmCopySelectedModelIds', {gridId});

    console.debug('[vdm][copy] hook ready:', {
        hasDashAgGrid: !!window.dash_ag_grid,
        apiFn:
            window.dash_ag_grid &&
            window.dash_ag_grid.getApi &&
            window.dash_ag_grid.getApi(gridId),
    });
    try {
        // dash-ag-grid registers itself as window.dash_ag_grid.
        const dag = window.dash_ag_grid;
        if (!dag || !dag.getApi) {
            throw new Error('Grid API not ready');
        }

        // Ensure the specific grid instance is available.
        const api = dag.getApi(gridId);
        if (!api) {
            throw new Error('Grid not ready');
        }
        const selected = api.getSelectedRows ? api.getSelectedRows() : [];
        const ids = (selected || []).map(r => r.id).filter(Boolean);

        if (!ids.length) {
            return { ok: false, message: 'Nothing selected' };
        }

        await navigator.clipboard.writeText(ids.join('\\n'));
        return { ok: true, message: 'Copied ' + ids.length + ' model IDs' };
    } catch (e) {
        return { ok: false, message: 'Copy failed: ' + (e && e.message ? e.message : String(e)) };
    }
};

// Copy a single string to clipboard
window.vdmCopyText = async function(text) {
    const value = (text == null) ? '' : String(text);
    if (!value) {
        return { ok: false, message: 'Nothing to copy' };
    }

    // Prefer the async clipboard API when available.
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(value);
            return { ok: true, message: 'Copied' };
        }
    } catch (e) {
        // Fall through to execCommand below.
    }

    // Fallback for contexts where clipboard API is unavailable/blocked.
    try {
        const ta = document.createElement('textarea');
        ta.value = value;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.left = '-1000px';
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, ta.value.length);
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return ok ? { ok: true, message: 'Copied' } : { ok: false, message: 'Copy failed' };
    } catch (e) {
        return { ok: false, message: 'Copy failed: ' + (e && e.message ? e.message : String(e)) };
    }
};

// Click-to-copy triggers a toast via a hidden Dash button.
// Clipboard copy is handled in the native AG Grid listener.

// Bridge from grid JS to the Dash toast renderer.
// Payload is stored on window.__vdm_last_toast_payload and a hidden trigger is clicked.
window.vdmToast = function(level, message, modelId) {
    try {
        window.__vdm_last_toast_payload = JSON.stringify({
            level: level || 'info',
            message: message || '',
            model_id: modelId,
        });
        const btn = document.getElementById('vdm-models-toast-trigger');
        if (btn) {
            btn.click();
        } else {
            console.debug('[vdm][toast] trigger not found');
        }
    } catch (e) {
        console.debug('[vdm][toast] failed', e);
    }
};



// Attach a native AG Grid cellClicked listener once the grid API is ready.
// This avoids relying on dashGridOptions "function" plumbing.
// (That indirection doesn't reliably invoke handlers.)
window.vdmAttachModelCellCopyListener = function(gridId) {
    try {
        const dag = window.dash_ag_grid;
        if (!dag || !dag.getApi) {
            return false;
        }
        const api = dag.getApi(gridId);
        if (!api) {
            return false;
        }

        // Idempotent attach (per grid instance).
        if (api.__vdmCopyListenerAttached) {
            return true;
        }
        api.__vdmCopyListenerAttached = true;
        console.log('[vdm][copy] attached model-id click listener', {gridId});

        api.addEventListener('cellClicked', async function(e) {
            try {
                if (!e || !e.colDef || e.colDef.field !== 'id') {
                    return;
                }
                const id = e.value;
                console.log('[vdm][copy] cellClicked', {id});

                // Copy here (this is the only path we have proven works reliably in your browser).
                const r = await window.vdmCopyText(String(id));
                if (r && r.ok) {
                    window.vdmToast('success', 'Copied model id: ' + String(id), id);
                } else {
                    window.vdmToast('warning', (r && r.message) ? r.message : 'Copy failed', id);
                }
            } catch (err) {
                console.log('[vdm][copy] cellClicked handler failed', err);
                window.vdmToast(
                    'warning',
                    'Copy failed: '
                        + (err && err.message ? err.message : String(err)),
                    null,
                );
            }
        });

        return true;
    } catch (_) {
        return false;
    }
};

// Attempt to attach immediately for the models grid.
// (The dashboard also has a boot loop that waits for dash_ag_grid.getApi.)
window.vdmAttachModelCellCopyListener('vdm-models-grid');

// dash-ag-grid expects functions under dashAgGridFunctions (kept for other formatters/comparators)
window.dashAgGridFunctions = window.dashAgGridFunctions || {};

// Utility function to escape HTML
window.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

"""


def get_ag_grid_clientside_callback() -> dict[str, dict[str, str]]:
    """Return the clientside callback for AG-Grid cell renderers."""
    # Note: the keys must match the Dash component id(s) of the AgGrid instances.
    return {"vdm-models-grid": {"javascript": CELL_RENDERER_SCRIPTS}}
