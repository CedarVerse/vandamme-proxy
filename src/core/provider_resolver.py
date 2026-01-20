"""Provider name resolution and validation.

Centralizes all provider-related operations to eliminate duplication
across the codebase.

This service provides a single source of truth for:
- Provider prefix parsing (provider:model format)
- Profile-aware resolution (profiles take precedence)
- Provider existence validation
- Default provider selection
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


class ProviderResolver:
    """Centralized provider resolution and validation.

    This service provides a single source of truth for:
    - Provider prefix parsing (provider:model format)
    - Profile-aware resolution (profiles take precedence)
    - Provider existence validation
    - Default provider selection

    Example:
        resolver = ProviderResolver(default_provider="openai", profile_manager=profile_mgr)
        provider, model = resolver.resolve_provider("anthropic:claude-3", available_providers)
    """

    def __init__(
        self,
        default_provider: str,
        profile_manager: ProfileManager | None = None,
    ) -> None:
        """Initialize resolver.

        Args:
            default_provider: Default provider name for fallback
            profile_manager: Optional profile manager for profile-aware resolution
        """
        self._default_provider = default_provider
        self._profile_manager = profile_manager

    def parse_provider_prefix(self, model: str) -> tuple[str | None, str]:
        """Extract provider prefix from model string.

        Args:
            model: Model name that may contain provider prefix (e.g., "openai:gpt-4")

        Returns:
            Tuple of (provider_name, model_without_prefix) or (None, model)
            Provider name is lowercased for consistency.
        """
        if ":" in model:
            provider, actual_model = model.split(":", 1)
            return provider.lower(), actual_model
        return None, model

    def resolve_provider(
        self,
        model: str,
        available_providers: dict[str, Any],
    ) -> tuple[str, str]:
        """Resolve provider from model with profile support.

        Resolution priority:
        1. Profile prefix (if profile_manager present) - checks profile aliases first
        2. Provider prefix in model name
        3. Default provider

        Args:
            model: Model name that may contain profile or provider prefix
            available_providers: Dict of available provider names

        Returns:
            Tuple of (provider_name, resolved_model)

        Raises:
            ValueError: If resolved provider not in available_providers
        """
        # Check for profile prefix FIRST
        if self._profile_manager and ":" in model:
            potential_profile, model_part = model.split(":", 1)
            if self._profile_manager.is_profile(potential_profile):
                profile = self._profile_manager.get_profile(potential_profile)
                # Check if model_part is in profile's aliases
                if profile and model_part in profile.aliases:
                    # Use the alias target (which includes provider prefix)
                    resolved_model = profile.aliases[model_part]
                    provider_name, actual_model = self.parse_provider_prefix(resolved_model)
                    if provider_name:
                        return self._validate_and_return(
                            provider_name, actual_model, available_providers
                        )
                # If not in profile aliases, fall through to normal resolution with model_part
                model = model_part

        # Check for provider prefix in model
        provider_name, actual_model = self.parse_provider_prefix(model)

        if provider_name:
            return self._validate_and_return(provider_name, actual_model, available_providers)

        # Use default provider
        return self._validate_and_return(self._default_provider, model, available_providers)

    def validate_provider_exists(
        self,
        provider_name: str,
        available_providers: dict[str, Any],
    ) -> None:
        """Validate provider exists, raise exception if not.

        Args:
            provider_name: Provider name to validate
            available_providers: Dict of available provider names

        Raises:
            ValueError: If provider not found
        """
        if provider_name not in available_providers:
            available = ", ".join(sorted(available_providers.keys()))
            raise ValueError(
                f"Provider '{provider_name}' not found. Available providers: {available}"
            )

    def get_provider_or_default(
        self,
        provider_candidate: str | None,
    ) -> str:
        """Get provider name or default, with normalization.

        Args:
            provider_candidate: Optional provider name (may be None)

        Returns:
            Normalized provider name (lowercased) or default_provider
        """
        if provider_candidate:
            return provider_candidate.lower()
        return self._default_provider

    def _validate_and_return(
        self,
        provider_name: str,
        model: str,
        available_providers: dict[str, Any],
    ) -> tuple[str, str]:
        """Validate provider and return tuple.

        Internal helper used by resolve_provider.

        Raises:
            ValueError: If provider not found in available_providers
        """
        self.validate_provider_exists(provider_name, available_providers)
        return provider_name, model
