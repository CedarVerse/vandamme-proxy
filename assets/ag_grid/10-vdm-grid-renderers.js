// Vandamme Dashboard - AG Grid Cell Renderers
// This file contains the cell renderer functions for AG Grid components.
// Loaded before helpers and init scripts.

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
            ''
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
            ''
        );
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return React.createElement(
            'span',
            {
                title: 'Only http(s) URLs allowed',
                style: { color: '#666', opacity: 0.3, fontSize: '16px' },
            },
            ''
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
        ''
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
