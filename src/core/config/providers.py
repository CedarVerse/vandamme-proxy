"""Provider configuration module.

This module handles provider-related configuration including:
- Default target resolution from environment, TOML, or system defaults
- Provider API key retrieval
- Provider base URL configuration

Now uses schema-based loading for default target configuration.
"""

import logging
import os
from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for provider-related settings.

    Attributes:
        default_target: The name of the default target (e.g., "openai", "anthropic", or a profile)
        default_target_source: Where the default target came from ("env", "toml", "system")
        default_target_api_key: The API key for the default target, if available
    """

    default_target: str
    default_target_source: str
    default_target_api_key: str | None


class ProviderSettings:
    """Manages provider configuration from environment and TOML files.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion
    - Validation with clear error messages
    - Single source of truth for default values
    """

    @staticmethod
    def _get_provider_api_key_env_var(provider: str) -> str:
        """Get the environment variable name for a provider's API key.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            Environment variable name (e.g., "OPENAI_API_KEY")
        """
        return f"{provider.upper()}_API_KEY"

    @staticmethod
    def _get_provider_base_url_env_var(provider: str) -> str:
        """Get the environment variable name for a provider's base URL.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            Environment variable name (e.g., "OPENAI_BASE_URL")
        """
        return f"{provider.upper()}_BASE_URL"

    @staticmethod
    def _get_default_base_url(provider: str) -> str:
        """Get the default base URL for a provider.

        Args:
            provider: Provider name (e.g., "openai", "poe")

        Returns:
            Default base URL for the provider
        """
        provider_upper = provider.upper()
        if provider_upper == "OPENAI":
            return "https://api.openai.com/v1"
        elif provider_upper == "POE":
            return "https://api.poe.com/v1"
        return "https://api.openai.com/v1"

    @staticmethod
    def resolve_default_target() -> tuple[str, str]:
        """Resolve default target from env, TOML, or system default.

        Checks sources in priority order:
        1. Environment variable VDM_DEFAULT_TARGET
        2. TOML configuration (default-target in defaults section)
        3. System default ("openai")

        Returns:
            Tuple of (target_name, source) where source is "env", "toml", or "system"
        """
        # Check environment variable first (highest priority)
        env_target = load_env_var(ConfigSchema.VDM_DEFAULT_TARGET)
        if env_target != "openai":  # If not the default, it was explicitly set
            logger.debug(f"Using default target from environment: {env_target}")
            return env_target, "env"

        # Try TOML configuration
        try:
            from src.core.alias_config import AliasConfigLoader

            loader = AliasConfigLoader()
            defaults = loader.get_defaults()
            toml_target = defaults.get("default-target")
            if toml_target:
                logger.debug(f"Using default target from TOML: {toml_target}")
                return toml_target, "toml"
        except Exception as e:
            logger.debug(f"Failed to load default target from TOML: {e}")

        # Fall back to system default
        logger.debug("Using system default target: openai")
        return env_target, "system"

    @staticmethod
    def get_provider_api_key(provider: str) -> str | None:
        """Get API key for a specific provider from environment.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            API key string if found, None otherwise
        """
        env_var = ProviderSettings._get_provider_api_key_env_var(provider)
        return os.environ.get(env_var)

    @staticmethod
    def get_provider_base_url(provider: str) -> str:
        """Get base URL for a specific provider.

        First checks the environment variable {PROVIDER}_BASE_URL,
        then falls back to provider-specific defaults.

        Args:
            provider: Provider name (e.g., "openai", "poe")

        Returns:
            Base URL for the provider
        """
        env_var = ProviderSettings._get_provider_base_url_env_var(provider)
        return os.environ.get(env_var, ProviderSettings._get_default_base_url(provider))

    @staticmethod
    def load() -> ProviderConfig:
        """Load provider configuration using schema-based validation.

        Returns:
            ProviderConfig with resolved default target and its API key

        Raises:
            ConfigError: If any environment variable fails validation
        """
        target, source = ProviderSettings.resolve_default_target()
        api_key = ProviderSettings.get_provider_api_key(target)

        # Note: Warning about missing API key is deferred to
        # ProviderManager._load_default_provider() where ProfileManager.is_profile()
        # is available to avoid false positives for profile names

        return ProviderConfig(
            default_target=target,
            default_target_source=source,
            default_target_api_key=api_key,
        )
