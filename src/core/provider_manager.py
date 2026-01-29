"""Provider management for multi-provider API support.

This module provides the ProviderManager class which serves as a facade
for managing multiple OpenAI/Anthropic clients for different providers
with automatic failover and API key rotation.

The ProviderManager implements the ProviderClientFactory protocol for
clean dependency inversion, eliminating circular imports.

Architecture:
    ProviderManager is a facade that delegates to focused components:
    - ProviderRegistry: Store and retrieve provider configurations
    - ApiKeyRotator: Thread-safe round-robin API key rotation
    - ClientFactory: Create and cache API client instances
    - DefaultProviderSelector: Select default provider with fallback
    - MiddlewareManager: Manage middleware chain lifecycle
    - ProviderConfigLoader: Load provider configs from env and TOML

Note: Configuration loading (~400 lines) remains in ProviderManager until
ProviderConfigLoader is enhanced to support [defaults] section fallback.
"""

import hashlib
import logging
import os
from typing import TYPE_CHECKING, Any, Union

from src.core.client import OpenAIClient
from src.core.exceptions import ConfigurationError
from src.core.protocols import ProviderClientFactory
from src.core.provider import (
    ApiKeyRotator,
    ClientFactory,
    DefaultProviderSelector,
    MiddlewareManager,
    ProviderConfigLoader,
    ProviderRegistry,
)
from src.core.provider.provider_config_loader import ProviderLoadResult
from src.core.provider_config import (
    OAUTH_SENTINEL,
    PASSTHROUGH_SENTINEL,
    AuthMode,
    ProviderConfig,
)

if TYPE_CHECKING:
    from typing import Any

    from rich.console import Console

    from src.core.alias_config import AliasConfigLoader
    from src.core.anthropic_client import AnthropicClient
    from src.core.config.middleware import MiddlewareConfig
    from src.core.profile_config import ProfileConfig
    from src.core.profile_manager import ProfileManager

logger = logging.getLogger(__name__)

# Lazy-loaded singleton for AliasConfigLoader
_alias_config_loader: "AliasConfigLoader | None" = None


class ProviderManager(ProviderClientFactory):
    """Facade for provider management using focused components.

    This class coordinates the following components:
    - ProviderRegistry: Stores and retrieves provider configurations
    - ApiKeyRotator: Manages thread-safe API key rotation
    - ClientFactory: Creates and caches API client instances
    - DefaultProviderSelector: Selects default provider with fallback
    - MiddlewareManager: Manages middleware chain lifecycle
    - ProviderConfigLoader: Loads provider configs from env and TOML

    The provider manager can be configured with an optional MiddlewareConfig
    to avoid circular dependencies with the global config singleton.

    This class implements the ProviderClientFactory protocol for clean
    dependency inversion.
    """

    def __init__(
        self,
        default_provider: str | None = None,
        default_provider_source: str | None = None,
        middleware_config: "MiddlewareConfig | None" = None,
        profile_manager: "ProfileManager | None" = None,
        provider_resolver: "Any" = None,  # ProviderResolver, but use Any to avoid circular import
        # Component injection (optional, for testing)
        registry: "ProviderRegistry | None" = None,
        api_key_rotator: "ApiKeyRotator | None" = None,
        client_factory: "ClientFactory | None" = None,
        default_selector: "DefaultProviderSelector | None" = None,
        middleware_manager: "MiddlewareManager | None" = None,
        config_loader: "ProviderConfigLoader | None" = None,
    ) -> None:
        # Store dependencies
        self._profile_manager = profile_manager
        self._provider_resolver = provider_resolver

        # Initialize components (or inject for testing)
        self._registry = registry or ProviderRegistry()
        self._api_key_rotator = api_key_rotator or ApiKeyRotator()
        self._client_factory = client_factory or ClientFactory()
        self._middleware_manager = middleware_manager or MiddlewareManager(middleware_config)
        self._config_loader = config_loader or ProviderConfigLoader()

        # Default provider selection
        default = default_provider if default_provider is not None else "openai"
        self._default_selector = default_selector or DefaultProviderSelector(
            default_provider=default,
            source=default_provider_source or "system",
        )

        # Load tracking
        self._load_results: list[ProviderLoadResult] = []
        self._loaded = False

    @property
    def default_provider(self) -> str:
        """Get the default provider name.

        This property is part of the ProviderClientFactory protocol.
        It can be modified internally by _select_default_from_available()
        but appears read-only to external code.
        """
        return self._default_selector.actual_default or self._default_selector.configured_default

    @property
    def configured_default(self) -> str:
        """Get the configured default provider name (from env/TOML).

        This is the default provider as configured by the user, without
        any fallback logic applied.
        """
        return self._default_selector.configured_default

    @property
    def actual_default(self) -> str | None:
        """Get the actual default provider being used (after fallback).

        This may differ from configured_default if the configured default
        provider is not available and a fallback was selected.
        """
        return self._default_selector.actual_default

    @property
    def default_provider_source(self) -> str:
        """Get the source of the default provider configuration."""
        return self._default_selector._source

    @property
    def _middleware_config(self) -> "Any | None":  # MiddlewareConfig | None
        """Get middleware config."""
        return self._middleware_manager._config

    @property
    def middleware_chain(self) -> "Any":
        """Get the middleware chain from MiddlewareManager."""
        return self._middleware_manager.middleware_chain

    @property
    def _middleware_initialized(self) -> bool:
        """Check if middleware is initialized."""
        return self._middleware_manager.is_initialized

    @_middleware_initialized.setter
    def _middleware_initialized(self, value: bool) -> None:
        """Setter for middleware_initialized (delegates to MiddlewareManager)."""
        # This is a no-op since the MiddlewareManager tracks its own state
        pass

    @property
    def _api_key_indices(self) -> dict[str, int]:
        """Get API key indices (compatibility shim for tests).

        This is a compatibility property during refactoring.
        Returns a copy from the internal ApiKeyRotator.
        """
        # Return the internal state from ApiKeyRotator for test compatibility
        return self._api_key_rotator._indices.copy()

    @property
    def profile_manager(self) -> "ProfileManager | None":
        """Get the profile manager instance.

        Returns:
            ProfileManager or None if not set
        """
        return self._profile_manager

    @staticmethod
    def get_api_key_hash(api_key: str) -> str:
        """Return first 8 chars of sha256 hash"""
        # Special handling for passthrough and OAuth sentinels
        if api_key == PASSTHROUGH_SENTINEL:
            return "PASSTHRU"
        if api_key == OAUTH_SENTINEL:
            return "OAUTH"
        # nosemgrep: py.weak-sensitive-data-hashing
        # SHA-256 first-8-char is appropriate for logging correlation IDs:
        # - Non-reversible: cannot recover original API key
        # - Stable: same key produces same hash across runs
        # - Purpose: debugging/incident correlation, not cryptography
        return hashlib.sha256(api_key.encode()).hexdigest()[:8]

    def _select_default_from_available(self) -> None:
        """Select a default provider from available providers if original default is unavailable.

        Delegates to DefaultProviderSelector for cleaner separation of concerns.
        Also syncs the legacy _default_provider attribute for backward compatibility.
        """
        selected = self._default_selector.select(
            dict(self._registry.list_all())  # type: ignore[arg-type]
        )
        # Update legacy attribute for backward compatibility
        self._default_provider = selected

    # ==================== AliasConfigLoader Singleton ====================

    def _get_alias_config_loader(self) -> "AliasConfigLoader":
        """Get or create the singleton AliasConfigLoader instance.

        Returns:
            The shared AliasConfigLoader instance.
        """
        global _alias_config_loader
        if _alias_config_loader is None:
            from src.core.alias_config import AliasConfigLoader

            _alias_config_loader = AliasConfigLoader()
        return _alias_config_loader

    # ==================== Phase 4: Provider Name Normalization ====================

    @staticmethod
    def _normalize_provider_name(provider_name: str) -> str:
        """Normalize provider name to lowercase for consistent handling.

        Args:
            provider_name: The provider name to normalize.

        Returns:
            The normalized (lowercase) provider name.
        """
        return provider_name.lower()

    # ==================== Phase 2: Auth Mode Detection Helper ====================

    def _detect_auth_mode(
        self,
        provider_name: str,
        toml_config: dict[str, Any],
    ) -> AuthMode:
        """Detect authentication mode (env var > sentinel > TOML).

        Priority order:
        1. Explicit {PROVIDER}_AUTH_MODE environment variable
        2. Sentinel values in API key (!OAUTH or !PASSTHRU)
        3. TOML configuration auth-mode setting

        Args:
            provider_name: Name of the provider.
            toml_config: Provider configuration from TOML files.

        Returns:
            The detected AuthMode (API_KEY, OAUTH, or PASSTHROUGH).
        """
        provider_upper = provider_name.upper()
        auth_mode = AuthMode.API_KEY

        # 1. Check explicit AUTH_MODE environment variable
        env_auth_mode = os.environ.get(f"{provider_upper}_AUTH_MODE", "").lower()
        if env_auth_mode == "oauth":
            return AuthMode.OAUTH
        elif env_auth_mode == "passthrough":
            return AuthMode.PASSTHROUGH

        # 2. Check for sentinel values in API key
        raw_api_key = os.environ.get(f"{provider_upper}_API_KEY") or toml_config.get("api-key", "")
        if raw_api_key == OAUTH_SENTINEL:
            return AuthMode.OAUTH
        elif raw_api_key == PASSTHROUGH_SENTINEL:
            return AuthMode.PASSTHROUGH

        # 3. Check TOML configuration auth-mode setting
        toml_auth_mode = toml_config.get("auth-mode", "").lower()
        if toml_auth_mode == "oauth":
            return AuthMode.OAUTH
        elif toml_auth_mode == "passthrough":
            return AuthMode.PASSTHROUGH

        return auth_mode

    # ==================== Configuration Fallback Helpers ====================

    @staticmethod
    def _get_config_with_fallback(
        toml_config: dict[str, Any],
        key: str,
        env_var: str,
        defaults_section: dict[str, Any],
        provider_name: str,
    ) -> int:
        """Get config value with fallback: env -> provider -> defaults -> fail fast.

        Special values:
        - 0 means "disabled" (e.g., no timeout, no retries) - valid and respected
        - None/null is invalid and raises ConfigurationError
        - If no value is found after checking all sources, raises ConfigurationError

        Args:
            toml_config: Provider-specific TOML config dict
            key: Config key to look up (e.g., "timeout", "max-retries")
            env_var: Environment variable name (e.g., "REQUEST_TIMEOUT")
            defaults_section: The [defaults] section from TOML
            provider_name: Name of the provider (for error messages)

        Returns:
            The resolved integer value

        Raises:
            ConfigurationError: If value is None/null, negative, or not defined
        """

        def parse_value(value: str | int | None, source: str) -> int | None:
            """Parse and validate a config value.

            Args:
                value: The value to parse (int, str, or None)
                source: Description of where the value came from (for error messages)

            Returns:
                The parsed integer value, or None if value is None

            Raises:
                ConfigurationError: If value is None/null, negative, or invalid
            """
            if value is None:
                return None  # Caller will fall through to next source

            if isinstance(value, int):
                if value < 0:
                    raise ConfigurationError(
                        f"Invalid {key} value in {source}: {value}. "
                        "Must be a non-negative integer "
                        "(0 disables the feature, null is an error)."
                    )
                return value

            if isinstance(value, str):
                value = value.strip()
                if value.lower() == "null":
                    raise ConfigurationError(
                        f"Invalid {key} value in {source}: 'null'. "
                        f"Use 0 to disable {key}, or remove the key to use fallback values."
                    )
                try:
                    int_value = int(value)
                    if int_value < 0:
                        raise ConfigurationError(
                            f"Invalid {key} value in {source}: {int_value}. "
                            f"Must be a non-negative integer."
                        )
                    return int_value
                except ValueError as e:
                    raise ConfigurationError(
                        f"Invalid {key} value in {source}: '{value}'. "
                        f"Must be an integer (0 to disable, or a positive number)."
                    ) from e

            return None

        # 1. Environment variable (highest priority)
        env_value = os.environ.get(env_var)
        if env_value is not None:
            result = parse_value(env_value, f"environment variable {env_var}")
            if result is not None:
                return result

        # 2. Provider-level TOML config
        provider_value = toml_config.get(key)
        if provider_value is not None:
            result = parse_value(provider_value, f"[{provider_name}] {key}")
            if result is not None:
                return result

        # 3. [defaults] section fallback
        defaults_value = defaults_section.get(key)
        if defaults_value is not None:
            result = parse_value(defaults_value, f"[defaults] {key}")
            if result is not None:
                return result

        # 4. No value found - fail fast with helpful error
        raise ConfigurationError(
            f"Required configuration '{key}' not found for provider '{provider_name}'. "
            f"Please define it in one of:\n"
            f"  1. Environment variable: {env_var}\n"
            f"  2. Provider config: [{provider_name}] {key} = <value>\n"
            f"  3. Global defaults: [defaults] {key} = <value>\n"
            f"Use 0 to disable {key}, or a positive integer to enable it."
        )

    def load_provider_configs(self) -> None:
        """Load all provider configurations from environment variables.

        Delegates to ProviderConfigLoader for actual loading logic.
        """
        if self._loaded:
            return

        # Reset load results
        self._load_results = []

        # Delegate loading to ProviderConfigLoader
        results = self._config_loader.load_all_providers(
            default_provider=self._default_selector.configured_default,
            default_selector=self._default_selector,
            registry=self._registry,
        )
        self._load_results = results

        # Validate at least one provider loaded successfully
        loaded_providers = [r for r in results if r.status == "success"]
        if not loaded_providers:
            available_providers = self._config_loader.scan_providers()
            raise ValueError(
                f"No providers configured. Set {available_providers} API keys or "
                f"configure providers in vandamme-config.toml"
            )

        # Select a default provider from available ones if needed
        self._select_default_from_available()

        self._loaded = True

        # Initialize middleware after loading providers
        self._initialize_middleware()

    def _initialize_middleware(self) -> None:
        """Initialize and register middleware based on loaded providers.

        Delegates to MiddlewareManager for cleaner separation of concerns.
        """
        # Delegate to MiddlewareManager
        self._middleware_manager.initialize_sync()
        self._middleware_initialized = self._middleware_manager.is_initialized

    async def initialize_middleware(self) -> None:
        """Asynchronously initialize the middleware chain.

        Delegates to MiddlewareManager for cleaner separation of concerns.
        """
        await self._middleware_manager.initialize()
        self._middleware_initialized = self._middleware_manager.is_initialized

    async def cleanup_middleware(self) -> None:
        """Cleanup middleware resources.

        Delegates to MiddlewareManager for cleaner separation of concerns.
        """
        await self._middleware_manager.cleanup()

    def parse_model_name(self, model: str) -> tuple[str, str]:
        """Parse 'provider:model' into (provider, model)

        Delegates to ProviderResolver for consistency when available.

        Returns:
            Tuple[str, str]: (provider_name, actual_model_name)
        """
        # Delegate to ProviderResolver if available (from dependency injection)
        if self._provider_resolver is not None:
            provider, actual_model = self._provider_resolver.parse_provider_prefix(model)
            if provider is None:
                provider = self.default_provider
            return provider, actual_model

        # Fallback to legacy implementation for backward compatibility
        if ":" in model:
            provider, actual_model = model.split(":", 1)
            return provider.lower(), actual_model
        return self.default_provider, model

    def get_client(
        self,
        provider_name: str,
        client_api_key: str
        | None = None,  # Client's API key for passthrough (unused, kept for compat)
    ) -> Union[OpenAIClient, "AnthropicClient"]:
        """Get or create a client for the specified provider.

        Delegates to ClientFactory for cleaner separation of concerns.
        The client_api_key parameter is kept for backward compatibility but
        is no longer used (clients are created with provider's API key).
        """
        if not self._loaded:
            self.load_provider_configs()

        # Ensure middleware is initialized when clients are accessed
        # Note: We can't await here, so we do sync initialization
        # The full async initialization should be called during app startup
        if not self._middleware_initialized:
            self._initialize_middleware()

        # Check if provider exists in registry (single source of truth)
        config = self._registry.get(provider_name)
        if config is None:
            raise ValueError(
                f"Provider '{provider_name}' not configured. "
                f"Available providers: {list(self._registry.list_all().keys())}"
            )

        # Delegate to ClientFactory
        return self._client_factory.get_or_create_client(config)

    async def get_next_provider_api_key(self, provider_name: str) -> str:
        """Return the next provider API key using process-global round-robin.

        Delegates to ApiKeyRotator for thread-safe rotation.

        Only valid for providers configured with static keys (not passthrough, not OAuth).
        """
        if not self._loaded:
            self.load_provider_configs()

        config = self._registry.get(provider_name)
        if config is None:
            raise ValueError(f"Provider '{provider_name}' not configured")
        if config.uses_passthrough or config.uses_oauth:
            raise ValueError(
                f"Provider '{provider_name}' uses {config.auth_mode} "
                f"authentication and has no static keys"
            )

        api_keys = config.get_api_keys()
        return await self._api_key_rotator.get_next_key(provider_name, api_keys)

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """Get configuration for a specific provider.

        Delegates to ProviderRegistry for cleaner separation of concerns.

        Args:
            provider_name: The name of the provider

        Returns:
            The ProviderConfig

        Raises:
            ValueError: If provider not found (for consistency with get_client)
        """
        if not self._loaded:
            self.load_provider_configs()
        config = self._registry.get(provider_name)
        if config is None:
            raise ValueError(
                f"Provider '{provider_name}' not configured. "
                f"Available providers: {list(self._registry.list_all().keys())}"
            )
        return config

    def list_providers(self) -> dict[str, ProviderConfig]:
        """List all configured providers.

        Delegates to ProviderRegistry for cleaner separation of concerns.
        """
        if not self._loaded:
            self.load_provider_configs()
        return self._registry.list_all()

    def get_effective_timeout(
        self, provider_name: str, profile: "ProfileConfig | None"
    ) -> int | None:
        """Get timeout for a provider, optionally overridden by profile.

        Args:
            provider_name: Provider to get config for
            profile: Active profile (optional)

        Returns:
            Timeout value in seconds, or None if provider not found
        """
        base_config = self._registry.get(provider_name)
        if base_config is None:
            return None

        if profile is not None and profile.timeout is not None:
            return profile.timeout
        return base_config.timeout

    def get_effective_max_retries(
        self, provider_name: str, profile: "ProfileConfig | None"
    ) -> int | None:
        """Get max-retries for a provider, optionally overridden by profile.

        Args:
            provider_name: Provider to get config for
            profile: Active profile (optional)

        Returns:
            Max retry count, or None if provider not found
        """
        base_config = self._registry.get(provider_name)
        if base_config is None:
            return None

        if profile is not None and profile.max_retries is not None:
            return profile.max_retries
        return base_config.max_retries

    def print_provider_summary(
        self, console: "Console | None" = None, is_default_profile: bool = False
    ) -> None:
        """Print a summary of loaded providers.

        Args:
            console: Rich Console instance for output. If None, creates a new one.
            is_default_profile: True if the default is a profile (not a provider).
                When True, no provider is marked with the default * indicator.

        Delegates to ProviderRegistry for config lookups.
        """
        if console is None:
            from rich.console import Console

            console = Console()

        if not self._loaded:
            self.load_provider_configs()

        # Always show the default provider, whether in _load_results or not
        all_results = self._load_results.copy()

        # Check if default provider is already in results
        default_in_results = any(r.name == self.default_provider for r in all_results)

        # If not, add it from registry
        if not default_in_results:
            default_config = self._registry.get(self.default_provider)
            if default_config:
                default_result = ProviderLoadResult(
                    name=self.default_provider,
                    status="success",
                    api_key_hash=self.get_api_key_hash(default_config.api_key),
                    base_url=default_config.base_url,
                )
                all_results.insert(0, default_result)  # Insert at beginning

        if not all_results:
            return

        print("\n📊 Active Providers:")
        print(f"   {'Status':<2} {'SHA256':<10} {'Name':<12} Base URL")
        print(f"   {'-' * 2} {'-' * 10} {'-' * 12} {'-' * 50}")

        success_count = 0

        for result in all_results:
            # Check if this is the default provider (only when not a profile default)
            is_default = not is_default_profile and result.name == self.default_provider
            default_indicator = "  * " if is_default else "    "

            # Check if this provider uses OAuth authentication
            provider_config = self._registry.get(result.name)
            is_oauth = provider_config and provider_config.uses_oauth
            oauth_indicator = "  🔐" if is_oauth else ""

            # nosemgrep: py.clear-text-logging-sensitive-data
            # api_key_hash is already hashed via get_api_key_hash() before logging
            # Raw API keys are never logged directly

            if result.status == "success":
                if is_default:
                    # Build format string for default provider (with color)
                    format_str = (
                        f"   ✅ {result.api_key_hash:<10}{default_indicator}"
                        f"\033[92m{result.name:<12}\033[0m {result.base_url}{oauth_indicator}"
                    )
                    print(format_str)
                else:
                    # Build format string for other providers
                    format_str = (
                        f"   ✅ {result.api_key_hash:<10}{default_indicator}"
                        f"{result.name:<12} {result.base_url}{oauth_indicator}"
                    )
                    print(format_str)
                success_count += 1
            else:  # partial
                if is_default:
                    # Build format string for partial default provider
                    format_str = (
                        f"   ⚠️ {result.api_key_hash:<10}{default_indicator}"
                        f"\033[92m{result.name:<12}\033[0m {result.message}{oauth_indicator}"
                    )
                    print(format_str)
                else:
                    # Build format string for partial other providers
                    format_str = (
                        f"   ⚠️ {result.api_key_hash:<10}{default_indicator}"
                        f"{result.name:<12} {result.message}{oauth_indicator}"
                    )
                    print(format_str)

        print(f"\n{success_count} provider{'s' if success_count != 1 else ''} ready for requests")
        if is_default_profile:
            print("  * = default provider (profile active, no default provider)")
        else:
            print("  * = default provider")
        print("  🔐 = OAuth authentication")

    def get_load_results(self) -> list[ProviderLoadResult]:
        """Get the load results for all providers"""
        if not self._loaded:
            self.load_provider_configs()
        return self._load_results.copy()
