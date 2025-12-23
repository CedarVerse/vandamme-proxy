"""JavaScript AG Grid cell renderers, utilities, and helpers.

This module exports the JS code that dash-ag-grid injects into the page via
clientside callbacks. The scripts are deliberately kept as a single large string
because dash-ag-grid expects that format.

Key exports:
- CELL_RENDERER_SCRIPTS: the main JS string
- get_ag_grid_clientside_callback(): maps grid IDs to the JS script
"""

CELL_RENDERER_SCRIPTS = """
console.info('[vdm] CELL_RENDERER_SCRIPTS loaded');

// ---- Row striping (all grids) ----
// Use AG Grid's built-in classes (`ag-row-even` / `ag-row-odd`) instead of custom
// rowClassRules so striping works without any grid-specific configuration.
(function ensureStripedRowsCss() {
    if (document.getElementById('vdm-striped-rows-css')) return;
    const style = document.createElement('style');
    style.id = 'vdm-striped-rows-css';
    style.textContent = `
      .ag-theme-alpine-dark .ag-row-even .ag-cell { background-color: rgba(255,255,255,0.06); }
      .ag-theme-alpine-dark .ag-row-odd  .ag-cell { background-color: rgba(0,0,0,0.00); }
    `;
    document.head.appendChild(style);
})();


// Render model id with optional icon.
// Contract: Python row shaping (`models_row_data`) must provide `model_icon_url`
// as either null/undefined or a safe http(s) URL string.
window.vdmModelIdWithIconRenderer = function(params) {
    const id = params && params.value ? String(params.value) : '';
    const url = params && params.data && params.data.model_icon_url;

    if (!url) {
        return React.createElement('span', null, id);
    }

    // Only allow http(s) URLs.
    let parsed;
    try {
        parsed = new URL(url);
    } catch (e) {
        return React.createElement('span', null, id);
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return React.createElement('span', null, id);
    }

    // Compact size aligned with existing row height.
    const img = React.createElement('img', {
        src: parsed.toString(),
        alt: '',
        width: 16,
        height: 16,
        style: {
            width: '16px',
            height: '16px',
            borderRadius: '3px',
            marginRight: '6px',
            verticalAlign: 'text-bottom',
            objectFit: 'cover',
        },
    });

    return React.createElement(
        'span',
        { style: { display: 'inline-flex', alignItems: 'center' } },
        img,
        React.createElement('span', null, id)
    );
};

// Render model page link as React element (Dash uses React; DOM nodes cause React invariant #31)
window.vdmModelPageLinkRenderer = function(params) {
    const url = params && params.data && params.data.model_page_url;

    if (!url) {
        return React.createElement(
            'span',
            {
                title: 'No model page available',
                style: { color: '#666', opacity: 0.3, fontSize: '16px' },
            },
            '🔗'
        );
    }

    // Only allow http(s) URLs to avoid accidentally creating javascript: links
    let parsed;
    try {
        parsed = new URL(url);
    } catch (e) {
        return React.createElement(
            'span',
            {
                title: 'Invalid model page URL',
                style: { color: '#666', opacity: 0.3, fontSize: '16px' },
            },
            '🔗'
        );
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return React.createElement(
            'span',
            {
                title: 'Only http(s) URLs allowed',
                style: { color: '#666', opacity: 0.3, fontSize: '16px' },
            },
            '🔗'
        );
    }

    // Open in a new tab for better UX
    return React.createElement(
        'a',
        {
            href: parsed.toString(),
            target: '_blank',
            rel: 'noopener noreferrer',
            style: { textDecoration: 'none', color: '#666' },
            title: 'Open model page',
        },
        '🔗'
    );
};


// Render a provider badge with Bootstrap-style colors
window.vdmProviderBadgeRenderer = function(params) {
    const provider = params && params.value ? String(params.value) : '';
    if (!provider) {
        return React.createElement('span', {}, '');
    }

    const color = (params.data && params.data.provider_color) || 'secondary';

    // Map Bootstrap color names to background colors
    const colorMap = {
        primary: '#0d6efd',
        secondary: '#6c757d',
        success: '#198754',
        info: '#0dcaf0',
        warning: '#ffc107',
        danger: '#dc3545',
    };
    const bgColor = colorMap[color] || colorMap.secondary;

    const style = {
        backgroundColor: bgColor,
        color: '#fff',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '11px',
        fontWeight: 500,
        display: 'inline-block',
    };

    return React.createElement('span', { style }, provider);
};


// Format a number with thousand separators
window.vdmFormattedNumberRenderer = function(params) {
    const value = params && params.value;
    if (value == null) {
        return React.createElement('span', {}, '');
    }

    const num = Number(value);
    if (isNaN(num)) {
        return React.createElement('span', {}, '');
    }

    const formatted = num.toLocaleString('en-US');
    return React.createElement('span', {}, formatted);
};


// Date comparator for sorting by ISO date strings
window.vdmDateComparator = function(date1, date2) {
    if (!date1) return date2 ? -1 : 0;
    if (!date2) return 1;

    const d1 = new Date(date1).getTime();
    const d2 = new Date(date2).getTime();

    if (isNaN(d1) && isNaN(d2)) return 0;
    if (isNaN(d1)) return -1;
    if (isNaN(d2)) return 1;

    return d1 - d2;
};


// Copy selected model IDs to clipboard
window.vdmCopySelectedModelIds = async function(gridId) {
    if (!gridId) {
        return { ok: false, message: 'No grid ID provided' };
    }

    // Wait up to 5 seconds for the grid API to become available
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
        const dag = window.dash_ag_grid;
        if (dag && dag.getApi) {
            const api = dag.getApi(gridId);
            if (api) {
                const selected = api.getSelectedRows ? api.getSelectedRows() : [];
                const ids = (selected || []).map(r => r.id).filter(Boolean);

                if (!ids.length) {
                    return { ok: false, message: 'Nothing selected' };
                }

                await navigator.clipboard.writeText(ids.join('\\n'));
                return { ok: true, message: 'Copied ' + ids.length + ' model IDs' };
            }
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    return { ok: false, message: 'Grid API not ready' };
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
        ta.style.position = 'absolute';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        const success = document.execCommand('copy');
        document.body.removeChild(ta);
        if (success) {
            return { ok: true, message: 'Copied' };
        }
        return { ok: false, message: 'Copy failed' };
    } catch (e) {
        return { ok: false, message: 'Copy failed: ' + (e && e.message ? e.message : String(e)) };
    }
};


// Show a toast notification by triggering a hidden Dash button
// The button click is bound to a Dash callback that shows a dbc.Toast
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

// Some dash-ag-grid versions also look under dashAgGridComponentFunctions for components.
window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// Register our custom cell renderers.
// dash-ag-grid resolves string component names via these global maps.
const vdmCellRenderers = {
    vdmModelPageLinkRenderer: window.vdmModelPageLinkRenderer,
    vdmModelIdWithIconRenderer: window.vdmModelIdWithIconRenderer,
};

for (const [name, fn] of Object.entries(vdmCellRenderers)) {
    if (typeof fn !== 'function') {
        console.warn('[vdm] cell renderer not found:', name);
        continue;
    }
    window.dashAgGridFunctions[name] = fn;
    window.dashAgGridComponentFunctions[name] = fn;

    // Expose as a global for debugging
    window['__' + name] = fn;
}

// Utility function to escape HTML
window.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};
"""


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
