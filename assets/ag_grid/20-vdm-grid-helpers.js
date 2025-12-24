// Vandamme Dashboard - AG Grid Helper Functions
// This file contains utility functions for AG Grid components.
// Loaded after renderers, before init script.

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


// Utility function to escape HTML
window.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};


// Format a duration given milliseconds, for display in AG Grid valueGetters.
// Keep in sync with Python `format_duration` semantics.
window.vdmFormatDurationValue = function(ms) {
    const n = Number(ms);
    if (!isFinite(n) || n <= 0) return '0s';

    const totalSeconds = Math.floor(n / 1000);
    if (totalSeconds <= 0) return '<1s';
    if (totalSeconds < 60) return `${totalSeconds}s`;

    const totalMinutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (totalMinutes < 60) {
        return seconds ? `${totalMinutes}m ${String(seconds).padStart(2, '0')}s` : `${totalMinutes}m`;
    }

    const totalHours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (totalHours < 24) {
        return minutes ? `${totalHours}h ${String(minutes).padStart(2, '0')}m` : `${totalHours}h`;
    }

    const days = Math.floor(totalHours / 24);
    const hours = totalHours % 24;
    return hours ? `${days}d ${String(hours).padStart(2, '0')}h` : `${days}d`;
};

window.vdmFormatDurationTooltip = function(ms) {
    const n = Number(ms);
    if (!isFinite(n) || n <= 0) return '0 ms';
    return `${Math.round(n).toLocaleString('en-US')} ms`;
};
