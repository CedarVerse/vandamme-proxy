from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash_ag_grid as dag  # type: ignore[import-untyped]
import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
from dash import html


def format_model_created_timestamp(timestamp: int | float | None) -> str | None:
    """Safely format model creation timestamp to ISO format.

    Handles large timestamps that might cause 'year out of range' errors.
    """
    if not timestamp:
        return None

    try:
        # Convert milliseconds to seconds if needed
        ts = timestamp / 1000 if timestamp > 1e12 else timestamp

        # Validate timestamp range (year 1 to 9999)
        if not (-62135596800 <= ts <= 253402300799):
            return None

        return datetime.fromtimestamp(ts).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def monospace(text: Any) -> html.Span:
    """Apply monospace font to text or span with style preservation."""
    if isinstance(text, html.Span):
        # If it's already a Span, just add the font family to existing style
        existing_style = getattr(text, "style", None) or {}
        existing_style = existing_style.copy() if isinstance(existing_style, dict) else {}

        existing_style["fontFamily"] = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"
        existing_class = getattr(text, "className", None)
        return html.Span(text.children, style=existing_style, className=existing_class)
    else:
        # Original behavior for non-Span values
        return html.Span(
            str(text), style={"fontFamily": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas"}
        )


def status_badge(*, status: str) -> dbc.Badge:
    s = (status or "unknown").lower()
    if s == "healthy":
        color = "success"
    elif s == "degraded":
        color = "warning"
    elif s in {"failed", "down", "error"}:
        color = "danger"
    else:
        color = "secondary"

    return dbc.Badge(status.upper(), color=color, pill=True)


def kpi_card(*, title: str, value: Any, subtitle: str | None = None) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(title, className="text-muted small"),
                html.Div(monospace(value), className="h3 mb-0"),
                html.Div(subtitle, className="text-muted small") if subtitle else None,
            ]
        ),
        className="h-100",
    )


def format_duration(ms: float) -> str:
    """Convert milliseconds to human-readable format."""
    if ms == 0:
        return "0ms"
    elif ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        seconds = ms / 1000
        return f"{seconds:.1f}s"
    else:
        minutes = ms / 60000
        return f"{minutes:.1f}m"


def format_timestamp(iso_string: str | None) -> str:
    """Convert ISO timestamp to relative time format with enhanced parsing."""
    if not iso_string:
        return "N/A"

    try:
        # Handle various ISO timestamp formats
        # Format with Z suffix
        if iso_string.endswith("Z"):
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        # Format with timezone offset
        elif "+" in iso_string[-6:] or "-" in iso_string[-6:]:
            dt = datetime.fromisoformat(iso_string)
        # Format without timezone info (assume local time)
        else:
            # Parse naive datetime and treat it as local time
            dt = datetime.fromisoformat(iso_string)
            now = datetime.now()
            # Compare naive datetimes in local time
            diff = now - dt

            # Handle future timestamps (clock skew)
            if diff.total_seconds() < 0:
                return "Just now"

            # Format as relative time
            if diff.total_seconds() < 60:
                return f"{int(diff.total_seconds())}s ago"
            elif diff.total_seconds() < 3600:
                return f"{int(diff.total_seconds() / 60)}m ago"
            elif diff.total_seconds() < 86400:
                return f"{int(diff.total_seconds() / 3600)}h ago"
            else:
                return f"{int(diff.total_seconds() / 86400)}d ago"

        # For timezone-aware timestamps, use UTC comparison
        now = datetime.now(timezone.utc)
        diff = now - dt

        # Handle future timestamps (clock skew)
        if diff.total_seconds() < 0:
            return "Just now"

        # Format as relative time
        if diff.total_seconds() < 60:
            return f"{int(diff.total_seconds())}s ago"
        elif diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() / 60)}m ago"
        elif diff.total_seconds() < 86400:
            return f"{int(diff.total_seconds() / 3600)}h ago"
        else:
            return f"{int(diff.total_seconds() / 86400)}d ago"
    except (ValueError, TypeError, AttributeError):
        return "Unknown"


def timestamp_with_hover(iso_string: str | None) -> html.Span:
    """Create a span with relative time display and absolute timestamp on hover."""
    relative_time = format_timestamp(iso_string)

    # Use the original iso_string for hover, or a default message
    hover_text = iso_string if iso_string else "No timestamp available"

    return html.Span(
        relative_time,
        title=hover_text,
        style={"cursor": "help", "textDecoration": "underline", "textDecorationStyle": "dotted"},
    )


def duration_color_class(ms: float) -> str:
    """Return CSS class for duration color coding."""
    if ms == 0:
        return "text-muted"
    elif ms < 500:
        return "text-success"
    elif ms < 2000:
        return "text-warning"
    else:
        return "text-danger"


def duration_cell(ms: float, show_raw: bool = True) -> html.Td:
    """Create a table cell with formatted duration and color coding."""
    if ms == 0:
        return html.Td(monospace("N/A"), className="text-muted")

    formatted = format_duration(ms)
    color_class = duration_color_class(ms)

    if show_raw:
        # Show both formatted and raw value
        return html.Td(
            html.Span(
                [
                    html.Span(formatted, className=color_class),
                    html.Span(f" ({ms:.0f}ms)", className="text-muted small ms-1"),
                ]
            )
        )
    else:
        return html.Td(html.Span(formatted, className=color_class))


def search_box(id: str, placeholder: str = "Search...", debounce: bool = True) -> dbc.Input:
    """Create a consistent search input with optional debouncing."""
    return dbc.Input(
        id=id,
        type="text",
        placeholder=placeholder,
        className="border-primary",
        debounce=debounce,
    )


def provider_badge(provider: str, color: str | None = None) -> dbc.Badge:
    """Create a styled provider badge.

    Rules:
    - Some well-known providers have fixed colors for consistent branding.
    - All other providers get a deterministic color derived from their name.
    """

    p = (provider or "").strip()
    key = p.lower()

    # Allow explicit override.
    if color:
        return dbc.Badge(p, color=color, pill=True, className="me-2")

    # Fixed colors for well-known providers.
    # NOTE: Colors must be valid Bootstrap theme colors.
    fixed: dict[str, str] = {
        # Blue-ish
        "openai": "primary",
        "openrouter": "info",
        # Anthropic uses danger now
        "anthropic": "danger",
        # Poe reuses success (green)
        "poe": "success",
    }

    fixed_color = fixed.get(key)
    if fixed_color:
        return dbc.Badge(p, color=fixed_color, pill=True, className="me-2")

    # Deterministic color for the rest.
    # We intentionally keep this simple (not cryptographic): sum of code points.
    palette: list[str] = [
        "primary",
        "success",
        "info",
        "warning",
        "danger",
        "secondary",
    ]
    idx = sum(ord(c) for c in key) % len(palette) if key else 0

    return dbc.Badge(p, color=palette[idx], pill=True, className="me-2")


def models_table(
    models: list[dict[str, Any]],
    sort_field: str = "id",
    sort_desc: bool = False,
    show_provider: bool = True,
) -> dag.AgGrid:
    """Create an AG-Grid table for models with advanced features.

    This function now returns an AG-Grid component instead of a Bootstrap table.
    The sort_field and sort_desc parameters are kept for backward compatibility
    but AG-Grid handles sorting internally through column headers.
    """
    from src.dashboard.components.ag_grid import models_ag_grid

    # Return AG-Grid component - sorting is now handled by clicking column headers
    # Note: grid_id is also used for selection/copy callbacks.
    return models_ag_grid(models=models, grid_id="vdm-models-grid")


def model_details_modal() -> dbc.Modal:
    """Modal for displaying full model details in card format."""
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("Model Details", className="text-white"), className="bg-dark"
            ),
            dbc.ModalBody(id="model-details-content", className="bg-dark text-white"),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-model-modal", className="btn-secondary", n_clicks=0),
                className="bg-dark",
            ),
        ],
        id="model-details-modal",
        is_open=False,
        size="lg",
        className="modal-dark",
    )


def model_details_drawer() -> dbc.Offcanvas:
    """Right-side drawer for displaying model details.

    The models grid supports multi-select (for copy IDs). The drawer is intended to
    show details for the *focused* row (typically the first selected row).

    Callback outputs:
    - Body: #vdm-model-details-body
    - Open state: #vdm-model-details-drawer.is_open
    """
    return dbc.Offcanvas(
        [
            html.Div(id="vdm-model-details-header"),
            html.Div(id="vdm-model-details-body"),
            dbc.Button(
                "Close",
                id="vdm-model-details-close",
                color="secondary",
                outline=True,
                size="sm",
                className="mt-3",
                n_clicks=0,
            ),
        ],
        id="vdm-model-details-drawer",
        title="Model details",
        is_open=False,
        placement="end",
        backdrop=True,
        scrollable=True,
        className="bg-dark text-white",
        style={"width": "min(560px, 92vw)"},
    )


def model_card(model: dict[str, Any], show_provider: bool = False) -> dbc.Card:
    """Create a reusable model display card."""
    card_content = [
        dbc.CardHeader(html.Strong(model.get("id", "Unknown Model"))),
        dbc.CardBody(
            [
                html.P(model.get("display_name", ""), className="card-text text-muted mb-2"),
                html.Small(
                    [
                        html.Span("Created: ", className="text-muted"),
                        timestamp_with_hover(format_model_created_timestamp(model.get("created"))),
                    ]
                ),
            ]
        ),
    ]

    if show_provider and model.get("provider"):
        card_content[1].children.insert(0, provider_badge(model["provider"]))

    return dbc.Card(card_content, className="h-100")


def alias_table(aliases: dict[str, Any]) -> dbc.Table:
    """Create a styled table for displaying aliases."""
    rows = []

    for provider, provider_aliases in aliases.items():
        if not isinstance(provider_aliases, dict):
            continue

        for alias_name, maps_to in provider_aliases.items():
            rows.append(
                html.Tr(
                    [
                        html.Td([provider_badge(provider), alias_name]),
                        html.Td(monospace(maps_to)),
                    ]
                )
            )

    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Alias"), html.Th("Maps To")]))] + [html.Tbody(rows)]
        if rows
        else [
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(
                                "No aliases configured",
                                colSpan=2,
                                className="text-center text-muted",
                            )
                        ]
                    )
                ]
            )
        ],
        striped=True,
        borderless=True,
        size="sm",
        responsive=True,
        className="table-dark",
    )


def token_display(count: int, label: str = "Tokens") -> html.Div:
    """Create a large, prominent token count display."""
    return html.Div(
        [
            html.Div(count, className="display-4 text-primary"),
            html.Div(label, className="text-muted small"),
        ],
        className="text-center",
    )


def empty_state(message: str, icon: str = "📋") -> html.Div:
    """Create a consistent empty state message."""
    return html.Div(
        [
            html.Div(icon, className="display-1 text-muted mb-3"),
            html.H4(message, className="text-muted"),
        ],
        className="text-center py-5",
    )


def loading_state() -> dbc.Spinner:
    """Create a consistent loading spinner."""
    return dbc.Spinner(color="primary", size="sm", type="border")
