"""Default provider selection with intelligent fallback.

The selector is *profile-aware*: if the configured default target is a profile
name rather than a real provider, it records the profile separately and falls
back to the first available real provider.  This allows downstream code to
distinguish between "user wants profile X" and "user wants provider X" while
still guaranteeing that ``select()`` always returns a usable provider name.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.profile_manager import ProfileManager


class DefaultProviderSelector:
    """Selects default provider with intelligent fallback.

    Responsibilities:
    - Validate configured default provider
    - Detect when the configured default is a *profile* rather than a provider
    - Fall back to first available provider if default unavailable
    - Raise helpful errors if no providers configured

    This class ensures that there is always a valid default provider available,
    or provides clear error messages if configuration is missing.

    Key invariant:
        ``_actual_default`` always contains a real provider name.
        ``_default_profile`` contains the profile name only when the configured
        default was detected as a profile.
    """

    def __init__(
        self,
        default_provider: str,
        source: str = "system",
        profile_manager: "ProfileManager | None" = None,
    ) -> None:
        """Initialize the default provider selector.

        Args:
            default_provider: The configured default provider name.
            source: The source of the configuration ("system", "env", "toml", etc.).
            profile_manager: Optional profile manager to detect profile names.
                When provided, the selector can distinguish between profile names
                and real provider names.  Imported under TYPE_CHECKING to avoid
                circular imports.
        """
        self._default = default_provider
        self._source = source
        self._profile_manager = profile_manager
        self._actual_default: str | None = None
        self._default_profile: str | None = None

    def select(self, available_providers: dict[str, object]) -> str:
        """Select default provider from available providers.

        Args:
            available_providers: Dictionary of available provider configurations.

        Returns:
            The selected provider name.

        Raises:
            ValueError: If no providers are available.
        """
        logger = logging.getLogger(__name__)

        # If the configured default is a profile name (not a real provider),
        # record it so callers can apply profile-specific configuration while
        # we still fall through to pick a real provider below.
        if (
            self._profile_manager
            and self._profile_manager.is_profile(self._default)
            and self._default not in available_providers
        ):
            self._default_profile = self._default
            logger.info(
                f"Configured default '{self._default}' is a profile, not a provider. "
                f"Will select first available provider for actual routing."
            )

        # If original default is available as a real provider, use it
        if self._default in available_providers:
            self._actual_default = self._default
            return self._default

        if available_providers:
            # Select the first available provider
            selected = list(available_providers.keys())[0]
            self._actual_default = selected

            if self._source != "system":
                # User configured a default but it's not available
                logger.info(
                    f"Using '{selected}' as default provider "
                    f"(configured '{self._default}' not available)"
                )
            else:
                # No user configuration, just pick the first available
                logger.debug(f"Using '{selected}' as default provider (first available provider)")
            return selected

        # No providers available at all
        provider_upper = self._default.upper()
        raise ValueError(
            f"No providers configured. Please set at least one provider API key "
            f"(e.g., {provider_upper}_API_KEY).\n"
            f"Hint: If {provider_upper}_API_KEY is set in your shell, make sure to export it: "
            f"'export {provider_upper}_API_KEY'"
        )

    @property
    def configured_default(self) -> str:
        """Get the configured default provider name."""
        return self._default

    @property
    def actual_default(self) -> str | None:
        """Get the actual default provider after selection."""
        return self._actual_default

    @property
    def default_profile(self) -> str | None:
        """Get the profile name if the configured default was a profile.

        Returns ``None`` when the configured default is a real provider or when
        ``select()`` has not been called yet.

        This is useful for downstream code that needs to apply profile-specific
        aliases or settings even though the selector fell back to a real
        provider for actual routing.
        """
        return self._default_profile
