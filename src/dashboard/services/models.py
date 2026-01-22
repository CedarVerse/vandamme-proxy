from __future__ import annotations

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


@dataclass(frozen=True)
class ProviderModelsView:
    row_data: list[dict[str, Any]]
    provider_options: list[dict[str, str]]
    provider_value: str | None
    hint: Any


@dataclass(frozen=True)
class ProfileModelsView:
    row_data: list[dict[str, Any]]
    profile_options: list[dict[str, str]]
    profile_value: str | None
    hint: Any  # Can be html.Span or list[html.Span | html.Any]


async def build_provider_models_view(*, cfg: Any, provider_value: str | None) -> ProviderModelsView:
    """Fetch models and build view fragments for the Provider Models tab."""

    health = await fetch_health(cfg=cfg)
    providers = await fetch_all_providers(cfg=cfg)

    default_provider = health.get("default_provider")
    if not isinstance(default_provider, str):
        default_provider = ""

    sorted_providers = sorted(p for p in providers if isinstance(p, str) and p)

    selected_provider = provider_value.strip() if provider_value else ""
    if not selected_provider:
        if default_provider:
            selected_provider = default_provider
        elif sorted_providers:
            selected_provider = sorted_providers[0]

    provider_options: list[dict[str, str]] = []
    if default_provider and default_provider in sorted_providers:
        provider_options.append(
            {"label": f"{default_provider} (default)", "value": default_provider}
        )

    provider_options.extend(
        [{"label": p, "value": p} for p in sorted_providers if p != default_provider]
    )

    hint = [
        html.Span("Listing models for "),
        provider_badge(selected_provider)
        if selected_provider
        else html.Span("(no providers)", className="text-muted"),
    ]

    models_data = await fetch_models(cfg=cfg, provider=selected_provider or None)
    models = models_data.get("data", [])

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
        )

    return ProviderModelsView(
        row_data=models_row_data(models),
        provider_options=provider_options,
        provider_value=selected_provider or None,
        hint=hint,
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
