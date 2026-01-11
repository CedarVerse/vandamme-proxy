"""Service layer for coordinating alias operations with provider filtering.

This service provides a clean separation between the domain layer (AliasManager)
and infrastructure layer (ProviderManager), eliminating circular dependencies
and improving testability.
"""

from logging import getLogger

from src.core.alias_manager import AliasManager
from src.core.provider_manager import ProviderManager

logger = getLogger(__name__)


class AliasService:
    """Service for alias operations with active provider filtering.

    This service coordinates between AliasManager (domain) and ProviderManager
    (infrastructure) to provide aliases filtered to only active providers.

    The service layer pattern eliminates circular dependencies that would occur
    if AliasManager directly imported ProviderManager, and makes testing easier
    by allowing both dependencies to be mocked explicitly.

    Args:
        alias_manager: The alias manager instance containing all alias definitions
        provider_manager: The provider manager instance for determining active providers

    Attributes:
        alias_manager: Alias manager for accessing all configured aliases
        provider_manager: Provider manager for determining which providers are active
    """

    def __init__(
        self,
        alias_manager: AliasManager,
        provider_manager: ProviderManager,
    ):
        self.alias_manager = alias_manager
        self.provider_manager = provider_manager

    def _get_active_provider_names(self) -> set[str]:
        """Get set of active provider names (those with API keys configured).

        Returns:
            Set of provider names that have API keys configured.
            Returns empty set if ProviderManager is not available or on error.

        Note:
            This method handles errors gracefully and logs them rather than
            raising exceptions, ensuring the service remains functional even
            when provider information is temporarily unavailable.
        """
        try:
            return set(self.provider_manager.list_providers().keys())
        except AttributeError as e:
            # ProviderManager not initialized - expected during early init
            logger.debug("ProviderManager not initialized: %s", e)
            return set()
        except Exception as e:
            # Unexpected error - log but don't crash
            logger.warning("Failed to get active providers: %s", e)
            return set()

    def get_active_aliases(self) -> dict[str, dict[str, str]]:
        """Get aliases filtered to only active providers.

        Returns:
            Dict mapping provider name to their aliases, filtered to only
            providers that have API keys configured. Empty dict if no
            providers are active or if provider filtering fails.

            Example:
                {
                    "openai": {"haiku": "gpt-4o-mini", "fast": "gpt-4o"},
                    "poe": {"sonnet": "glm-4.6"},
                }

        Note:
            If provider filtering fails (e.g., ProviderManager not initialized),
            this returns an empty dict rather than all aliases. This ensures
            the API only shows aliases that are actually usable.
        """
        active_providers = self._get_active_provider_names()

        if not active_providers:
            return {}

        all_aliases = self.alias_manager.get_all_aliases()

        return {
            provider: aliases.copy()
            for provider, aliases in all_aliases.items()
            if provider in active_providers
        }

    def print_alias_summary(self, default_provider: str | None = None) -> None:
        """Print a summary of configured aliases for active providers.

        This method displays an elegant, color-coded summary of all model aliases
        grouped by provider, showing only providers that are active (have API keys
        configured).

        Args:
            default_provider: Optional default provider to highlight in output.
                Used for showing usage examples.
        """
        # Get active aliases (filtered to providers with API keys)
        active_aliases = self.get_active_aliases()

        if not active_aliases:
            return

        # Get fallback aliases for type display
        fallback_aliases = self.alias_manager._fallback_aliases

        total_aliases = sum(len(aliases) for aliases in active_aliases.values())

        # Count fallback aliases
        total_fallbacks = sum(
            sum(1 for alias in aliases if alias in fallback_aliases.get(provider, set()))
            for provider, aliases in active_aliases.items()
        )

        print(
            f"\n✨ Model Aliases ({total_aliases} configured across "
            f"{len(active_aliases)} providers):"
        )

        if total_fallbacks > 0:
            print(f"   📦 Includes {total_fallbacks} fallback defaults from configuration")

        # Color code providers (using ANSI codes for terminal output)
        provider_colors = {
            "openai": "\033[94m",  # Blue
            "anthropic": "\033[92m",  # Green
            "azure": "\033[93m",  # Yellow
            "poe": "\033[95m",  # Magenta
            "bedrock": "\033[96m",  # Cyan
            "vertex": "\033[97m",  # White
            "gemini": "\033[91m",  # Red
        }

        # Sort providers by name for consistent display
        for provider in sorted(active_aliases.keys()):
            provider_aliases = active_aliases[provider]
            color = provider_colors.get(provider.lower(), "")
            reset = "\033[0m" if color else ""
            provider_display = f"{color}{provider}{reset}"

            provider_fallbacks = fallback_aliases.get(provider, {})
            num_fallback = sum(1 for alias in provider_aliases if alias in provider_fallbacks)

            provider_info = f"{provider_display} ({len(provider_aliases)} aliases"
            if num_fallback > 0:
                provider_info += f", {num_fallback} fallbacks"
            provider_info += "):"

            print(f"\n   {provider_info}")
            print(f"   {'Alias':<20} {'Target Model':<40} {'Type'}")
            print(f"   {'-' * 20} {'-' * 40} {'-' * 10}")

            # Sort aliases within each provider
            for alias, target in sorted(provider_aliases.items(), key=lambda x: x[0].lower()):
                # Determine if this is a fallback alias
                alias_type = "fallback" if alias in provider_fallbacks else "explicit"
                type_display = (
                    f"\033[90m{alias_type}\033[0m" if alias_type == "fallback" else alias_type
                )

                # Truncate long model names
                model_display = target
                if len(model_display) > 38:
                    model_display = model_display[:35] + "..."
                print(f"   {alias:<20} {model_display:<40} {type_display}")

        # Add usage examples
        print("\n   💡 Use aliases in your requests:")
        if active_aliases:
            # Try to use the default provider for the example
            example_provider = default_provider if default_provider in active_aliases else None
            if not example_provider:
                # Fall back to the first provider with aliases (alphabetically)
                example_provider = sorted(active_aliases.keys())[0]

            first_alias = sorted(active_aliases[example_provider].keys())[0]
            first_target = active_aliases[example_provider][first_alias]
            is_fallback = first_alias in fallback_aliases.get(example_provider, {})

            print(
                f"      Example: model='{first_alias}' → resolves to "
                f"'{example_provider}:{first_target}'"
            )
            if is_fallback:
                print("                (from configuration defaults)")
        print("      Substring matching: 'my-{alias}-model' matches alias '{alias}'")
        print("      Configure <PROVIDER>_ALIAS_<NAME> environment variables to create aliases")
        print("      Or override defaults in vandamme-config.toml")
