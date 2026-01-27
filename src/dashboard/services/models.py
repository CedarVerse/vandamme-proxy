from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from dash import html

from src.dashboard.components.ag_grid import models_row_data
from src.dashboard.components.ui import provider_badge
from src.dashboard.data_sources import (
    fetch_all_providers,
    fetch_health,
    fetch_models,
    fetch_profiles,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderModelsView:
    row_data: list[dict[str, Any]]
    provider_options: list[dict[str, str]]
    provider_value: str | None
    hint: Any
    models_url: str | None = None
    error_message: str | None = None
    error_type: str | None = None


@dataclass(frozen=True)
class ProfileModelsView:
    row_data: list[dict[str, Any]]
    profile_options: list[dict[str, str]]
    profile_value: str | None
    hint: Any  # Can be html.Span or list[html.Span | html.Any]


def _classify_error(error_message: str) -> str:
    """Classify error type from message.

    Returns error type string for UI display and icon selection.
    """
    msg_lower = error_message.lower()
    if "timeout" in msg_lower:
        return "timeout"
    if "connection" in msg_lower or "connect" in msg_lower:
        return "connection"
    if "401" in msg_lower or "403" in msg_lower or "auth" in msg_lower:
        return "auth"
    if "404" in msg_lower:
        return "not_found"
    if "502" in msg_lower or "503" in msg_lower or "500" in msg_lower:
        return "server_error"
    return "unknown"


def _format_error_message(
    error_message: str,
    provider: str | None,
) -> str:
    """Format error message with provider context.

    Extracts the core error message from DashboardDataError which already
    includes provider context, and formats it for display.
    """
    # The error message already has provider context from fetch_models()
    # Just return it as-is for display
    return error_message


async def build_provider_models_view(*, cfg: Any, provider_value: str | None) -> ProviderModelsView:
    """Fetch models and build view fragments for the Provider Models tab."""

    health = await fetch_health(cfg=cfg)
    providers = await fetch_all_providers(cfg=cfg)

    default_provider = health.get("default_provider")
    if not isinstance(default_provider, str):
        default_provider = ""

    sorted_providers = sorted(p for p in providers if isinstance(p, str) and p)

    # Build provider options first (needed for dropdown)
    provider_options: list[dict[str, str]] = []
    if default_provider and default_provider in sorted_providers:
        provider_options.append(
            {"label": f"{default_provider} (default)", "value": default_provider}
        )

    provider_options.extend(
        [{"label": p, "value": p} for p in sorted_providers if p != default_provider]
    )

    # If no provider selected, return empty state (don't auto-select or fetch)
    if not provider_value:
        return ProviderModelsView(
            row_data=[],
            provider_options=provider_options,
            provider_value=None,
            hint=html.Span("Select a provider to view available models", className="text-muted"),
            models_url=None,
            error_message=None,
        )

    # Provider selected - proceed with model fetch
    selected_provider = provider_value.strip()

    hint = [
        html.Span("Listing models for "),
        provider_badge(selected_provider),
    ]

    # Get models_url from health endpoint
    providers_dict = health.get("providers", {})
    provider_info = (
        providers_dict.get(selected_provider, {}) if isinstance(providers_dict, dict) else {}
    )
    models_url = provider_info.get("models_url") if isinstance(provider_info, dict) else None

    # Fetch models with error handling
    try:
        models_data = await fetch_models(cfg=cfg, provider=selected_provider or None)
        models = models_data.get("data", [])
    except Exception as e:
        # Classify and format error for elegant display
        error_message = str(e)
        error_type = _classify_error(error_message)
        formatted_error = _format_error_message(error_message, selected_provider)

        logger.debug(
            f"Failed to fetch models for {selected_provider}: {e}",
            extra={"error_type": error_type, "provider": selected_provider},
        )

        return ProviderModelsView(
            row_data=[],
            provider_options=provider_options,
            provider_value=selected_provider or None,
            hint=hint,
            models_url=models_url,
            error_message=formatted_error,
            error_type=error_type,
        )

    inferred_provider = selected_provider or default_provider or "multiple"
    for model in models:
        if not model.get("provider"):
            model["provider"] = inferred_provider

    if not models:
        return ProviderModelsView(
            row_data=[],
            provider_options=provider_options,
            provider_value=selected_provider or None,
            hint=hint,
            models_url=models_url,
            error_message=None,
        )

    return ProviderModelsView(
        row_data=models_row_data(models),
        provider_options=provider_options,
        provider_value=selected_provider or None,
        hint=hint,
        models_url=models_url,
        error_message=None,
    )


async def build_profile_models_view(*, cfg: Any, profile_value: str | None) -> ProfileModelsView:
    """Fetch models and build view fragments for the Profile Models tab."""

    # Fetch profiles list
    profiles_data = await fetch_profiles(cfg=cfg)
    profiles = [p["name"] for p in profiles_data.get("data", [])]

    # Build dropdown options
    sorted_profiles = sorted(profiles)
    profile_options: list[dict[str, str]] = [{"label": p, "value": p} for p in sorted_profiles]

    # Default selection (first profile or None)
    selected = profile_value or (sorted_profiles[0] if sorted_profiles else None)

    # Fetch models for selected profile (using # prefix)
    row_data: list[dict[str, Any]] = []
    hint: Any = html.Span("Select a profile", className="text-muted")

    if selected:
        models_data = await fetch_models(cfg=cfg, provider=f"#{selected}")
        models = models_data.get("data", [])

        # Add profile context to models
        for model in models:
            if not model.get("provider"):
                model["provider"] = selected

        row_data = models_row_data(models)
        hint = [html.Span("Profile: "), provider_badge(selected)]

    return ProfileModelsView(
        row_data=row_data,
        profile_options=profile_options,
        profile_value=selected,
        hint=hint,
    )
