"""Provider configuration loading from environment and TOML files."""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.core.exceptions import ConfigurationError
from src.core.provider_config import (
    OAUTH_SENTINEL,
    PASSTHROUGH_SENTINEL,
    AuthMode,
    ProviderConfig,
)

if TYPE_CHECKING:
    from src.core.alias_config import AliasConfigLoader

# Module-level cache for AliasConfigLoader singleton
_alias_config_loader: "AliasConfigLoader | None" = None


@dataclass
class ProviderLoadResult:
    """Result of loading a provider configuration."""

    name: str
    status: str  # "success", "partial"
    message: str | None = None
    api_key_hash: str | None = None
    base_url: str | None = None


class ProviderConfigLoader:
    """Loads provider configurations from environment variables and TOML files.

    Responsibilities:
    - Scan environment for {PROVIDER}_API_KEY patterns
    - Load TOML configurations via AliasConfigLoader
    - Merge env vars with TOML defaults
    - Parse provider-specific headers
    """

    def __init__(self) -> None:
        """Initialize a new provider config loader."""
        self._logger = logging.getLogger(__name__)

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

    def _get_config_with_fallback(
        self,
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

    def scan_providers(self) -> list[str]:
        """Scan environment for all providers with API keys configured.

        Returns:
            List of provider names (lowercase) that have API keys configured.
        """
        providers = []
        for env_key in os.environ:
            if env_key.endswith("_API_KEY") and not env_key.startswith("CUSTOM_"):
                provider_name = env_key[:-8].lower()  # Remove "_API_KEY" suffix
                providers.append(provider_name)
        return providers

    def get_custom_headers(self, provider_prefix: str) -> dict[str, str]:
        """Extract provider-specific custom headers from environment.

        Args:
            provider_prefix: The uppercase provider prefix (e.g., "OPENAI").

        Returns:
            Dictionary of header names to values.
        """
        custom_headers = {}
        provider_prefix = provider_prefix.upper()
        env_vars = dict(os.environ)

        for env_key, env_value in env_vars.items():
            if env_key.startswith(f"{provider_prefix}_CUSTOM_HEADER_"):
                # Convert PROVIDER_CUSTOM_HEADER_KEY to Header-Key
                header_name = env_key[
                    len(provider_prefix) + 15 :
                ]  # Remove 'PROVIDER_CUSTOM_HEADER_' prefix

                if header_name:  # Make sure it's not empty
                    # Convert underscores to hyphens for HTTP header format
                    header_name = header_name.replace("_", "-")
                    custom_headers[header_name] = env_value

        return custom_headers

    def load_toml_config(self, provider_name: str) -> dict[str, Any]:
        """Load provider configuration from TOML files.

        Args:
            provider_name: Name of the provider (e.g., "poe", "openai").

        Returns:
            Provider configuration dictionary from TOML.
        """
        try:
            from src.core.alias_config import AliasConfigLoader

            loader = AliasConfigLoader()
            return loader.get_provider_config(provider_name)
        except ImportError:
            self._logger.debug(f"AliasConfigLoader not available for provider '{provider_name}'")
            return {}
        except Exception as e:
            self._logger.debug(f"Failed to load TOML config for provider '{provider_name}': {e}")
            return {}

    def load_provider(
        self,
        provider_name: str,
        *,
        require_api_key: bool = True,
    ) -> ProviderConfig | None:
        """Load a single provider configuration.

        Args:
            provider_name: The name of the provider (lowercase).
            require_api_key: If True, raises ValueError when API key is missing.
                If False, returns None when API key is missing.

        Returns:
            ProviderConfig if loaded successfully, None if not found and
            require_api_key is False.

        Raises:
            ValueError: If provider is required but not found or misconfigured.
        """
        provider_upper = provider_name.upper()
        toml_config = self.load_toml_config(provider_name)

        # API key from env or TOML
        raw_api_key = os.environ.get(f"{provider_upper}_API_KEY") or toml_config.get("api-key")
        if not raw_api_key:
            if require_api_key:
                raise ValueError(
                    f"API key not found for provider '{provider_name}'. "
                    f"Please set {provider_upper}_API_KEY environment variable."
                )
            return None

        # Support multiple static keys, whitespace-separated
        api_keys = raw_api_key.split()
        if len(api_keys) == 0:
            if require_api_key:
                raise ValueError(
                    f"API key not found for provider '{provider_name}'. "
                    f"Please set {provider_upper}_API_KEY environment variable."
                )
            return None

        if len(api_keys) > 1 and PASSTHROUGH_SENTINEL in api_keys:
            raise ValueError(
                f"Provider '{provider_name}' has mixed configuration: "
                f"'!PASSTHRU' cannot be combined with static keys"
            )

        api_key = api_keys[0]

        # Base URL with precedence: env > TOML > default
        base_url = os.environ.get(f"{provider_upper}_BASE_URL") or toml_config.get("base-url")
        if not base_url:
            # Apply provider-specific defaults for backward compatibility
            if provider_name == "openai":
                base_url = "https://api.openai.com/v1"
            elif require_api_key:
                raise ValueError(
                    f"Base URL not found for provider '{provider_name}'. "
                    f"Please set {provider_upper}_BASE_URL environment variable "
                    f"or configure in vandamme-config.toml"
                )
            else:
                # For optional providers, return None if base URL is missing
                return None

        # API format
        api_format = os.environ.get(
            f"{provider_upper}_API_FORMAT", toml_config.get("api-format", "openai")
        )
        if api_format not in ("openai", "anthropic"):
            api_format = "openai"

        # Detect OAuth mode (priority order: env var > sentinel > TOML)
        auth_mode = AuthMode.API_KEY
        # 1. Check explicit AUTH_MODE environment variable
        env_auth_mode = os.environ.get(f"{provider_upper}_AUTH_MODE", "").lower()
        if env_auth_mode == "oauth":
            auth_mode = AuthMode.OAUTH
        elif env_auth_mode == "passthrough":
            auth_mode = AuthMode.PASSTHROUGH
        # 2. Check for !OAUTH sentinel in api_key
        elif api_key == OAUTH_SENTINEL or toml_config.get("auth-mode", "").lower() == "oauth":
            auth_mode = AuthMode.OAUTH
        elif toml_config.get("auth-mode", "").lower() == "passthrough":
            auth_mode = AuthMode.PASSTHROUGH

        # For OAuth mode, set empty API key (will use tokens instead)
        if auth_mode == AuthMode.OAUTH:
            api_key = ""
            api_keys = None

        # Other settings
        timeout = int(os.environ.get("REQUEST_TIMEOUT", toml_config.get("timeout", "90")))
        max_retries = int(os.environ.get("MAX_RETRIES", toml_config.get("max-retries", "2")))

        # Models documentation URL
        models_url = os.environ.get(f"{provider_upper}_MODELS_URL") or toml_config.get("models-url")

        return ProviderConfig(
            name=provider_name,
            api_key=api_key,
            api_keys=api_keys if len(api_keys) > 1 else None,
            base_url=base_url,
            api_version=os.environ.get(f"{provider_upper}_API_VERSION")
            or toml_config.get("api-version"),
            timeout=timeout,
            max_retries=max_retries,
            custom_headers=self.get_custom_headers(provider_upper),
            api_format=api_format,
            tool_name_sanitization=bool(toml_config.get("tool-name-sanitization", False)),
            auth_mode=auth_mode,
            models_url=models_url,
        )

    def load_provider_with_result(self, provider_name: str) -> ProviderLoadResult | None:
        """Load configuration for a specific provider and track the result.

        This is similar to load_provider but returns a ProviderLoadResult
        that can be used for reporting load status.

        Args:
            provider_name: The name of the provider (lowercase).

        Returns:
            ProviderLoadResult if provider was found, None otherwise.
        """
        provider_upper = provider_name.upper()
        toml_config = self.load_toml_config(provider_name)

        raw_api_key = os.environ.get(f"{provider_upper}_API_KEY") or toml_config.get("api-key")
        if not raw_api_key:
            return None

        api_keys = raw_api_key.split()
        if len(api_keys) == 0:
            return None

        if len(api_keys) > 1 and PASSTHROUGH_SENTINEL in api_keys:
            raise ValueError(
                f"Provider '{provider_name}' has mixed configuration: "
                f"'!PASSTHRU' cannot be combined with static keys"
            )

        api_key = api_keys[0]

        base_url = os.environ.get(f"{provider_upper}_BASE_URL") or toml_config.get("base-url")

        if not base_url:
            # Return partial result
            return ProviderLoadResult(
                name=provider_name,
                status="partial",
                message=(
                    f"Missing {provider_upper}_BASE_URL (configure in environment or "
                    "vandamme-config.toml)"
                ),
                api_key_hash=self._get_api_key_hash(api_key),
                base_url=None,
            )

        # Success
        return ProviderLoadResult(
            name=provider_name,
            status="success",
            api_key_hash=self._get_api_key_hash(api_key),
            base_url=base_url,
        )

    @staticmethod
    def _get_api_key_hash(api_key: str) -> str:
        """Return first 8 chars of sha256 hash."""
        import hashlib

        if api_key == PASSTHROUGH_SENTINEL:
            return "PASSTHRU"
        return hashlib.sha256(api_key.encode()).hexdigest()[:8]

    # ==================== Auth Mode Detection ====================

    @staticmethod
    def _detect_auth_mode(
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

    # ==================== Provider Name Normalization ====================

    @staticmethod
    def _normalize_provider_name(provider_name: str) -> str:
        """Normalize provider name to lowercase for consistent handling.

        Args:
            provider_name: The provider name to normalize.

        Returns:
            The normalized (lowercase) provider name.
        """
        return provider_name.lower()

    # ==================== Provider Loading Methods ====================

    def load_all_providers(
        self,
        default_provider: str | None,
        default_selector: "Any",  # DefaultProviderSelector, but use Any to avoid circular import
        registry: "Any",  # ProviderRegistry
    ) -> list[ProviderLoadResult]:
        """Load all provider configurations from environment and TOML.

        This is the main entry point for provider loading. It loads the default
        provider first, then loads additional providers from TOML and environment.

        Args:
            default_provider: Configured default provider name.
            default_selector: DefaultProviderSelector instance for intelligent fallback.
            registry: ProviderRegistry to register loaded configs.

        Returns:
            List of load results with success/failure status for each provider.
        """
        results = []

        # 1. Load default provider
        default_result = self._load_default_provider(
            default_provider,
            default_selector,
            registry,
        )
        if default_result is not None:
            results.append(default_result)

        # 2. Load additional providers from environment and TOML
        additional_results = self._load_additional_providers(
            default_provider,
            registry,
        )
        results.extend(additional_results)

        return results

    def _load_default_provider(
        self,
        default_provider: str | None,
        default_selector: "Any",  # DefaultProviderSelector
        registry: "Any",  # ProviderRegistry
    ) -> ProviderLoadResult | None:
        """Load the default provider configuration.

        Args:
            default_provider: The configured default provider name.
            default_selector: DefaultProviderSelector instance.
            registry: ProviderRegistry to register the config.

        Returns:
            ProviderLoadResult if provider was loaded, None if skipped.
        """
        if default_provider is None:
            return None

        provider_upper = default_provider.upper()
        toml_config = self.load_toml_config(default_provider)

        # Detect auth mode
        auth_mode = self._detect_auth_mode(default_provider, toml_config)

        # Check for API key (unless OAuth mode)
        raw_api_key = os.environ.get(f"{provider_upper}_API_KEY") or toml_config.get("api-key")
        if not raw_api_key:
            if auth_mode != AuthMode.OAUTH:
                # No API key and not OAuth mode - skip
                return None
            raw_api_key = ""  # OAuth mode uses empty API key

        # Support multiple static keys
        api_keys = raw_api_key.split()
        if len(api_keys) == 0:
            return None
        if len(api_keys) > 1 and PASSTHROUGH_SENTINEL in api_keys:
            raise ValueError(
                f"Provider '{default_provider}' has mixed configuration: "
                f"'!PASSTHRU' cannot be combined with static keys"
            )

        api_key = api_keys[0]

        # Get base URL with precedence: env > TOML > default
        base_url = os.environ.get(f"{provider_upper}_BASE_URL") or toml_config.get("base-url")
        if not base_url:
            # Apply provider-specific defaults for backward compatibility
            if default_provider == "openai":
                base_url = "https://api.openai.com/v1"
            else:
                # Return partial result
                return ProviderLoadResult(
                    name=default_provider,
                    status="partial",
                    message=(
                        f"Missing {provider_upper}_BASE_URL (configure in environment or "
                        "vandamme-config.toml)"
                    ),
                    api_key_hash=self._get_api_key_hash(api_key),
                    base_url=None,
                )

        # Get defaults section for fallback
        defaults_section = self._get_alias_config_loader().get_defaults()

        # Load timeout and max-retries with fallback chain
        timeout = self._get_config_with_fallback(
            toml_config=toml_config,
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section=defaults_section,
            provider_name=default_provider,
        )
        max_retries = self._get_config_with_fallback(
            toml_config=toml_config,
            key="max-retries",
            env_var="MAX_RETRIES",
            defaults_section=defaults_section,
            provider_name=default_provider,
        )

        # Get API format
        api_format = os.environ.get(
            f"{provider_upper}_API_FORMAT", toml_config.get("api-format", "openai")
        )
        if api_format not in ("openai", "anthropic"):
            api_format = "openai"

        # Create config
        config = ProviderConfig(
            name=default_provider,
            api_key=api_key,
            api_keys=api_keys if len(api_keys) > 1 else None,
            base_url=base_url,
            api_version=os.environ.get(f"{provider_upper}_API_VERSION")
            or toml_config.get("api-version"),
            timeout=timeout,
            max_retries=max_retries,
            custom_headers=self.get_custom_headers(provider_upper),
            api_format=api_format,
            tool_name_sanitization=bool(toml_config.get("tool-name-sanitization", False)),
            auth_mode=auth_mode,
            models_url=os.environ.get(f"{provider_upper}_MODELS_URL")
            or toml_config.get("models-url"),
        )

        # Register to provider registry
        registry.register(config)

        # Return load result
        return ProviderLoadResult(
            name=default_provider,
            status="success",
            api_key_hash=self._get_api_key_hash(api_key),
            base_url=base_url,
        )

    def _load_additional_providers(
        self,
        default_provider: str | None,
        registry: "Any",  # ProviderRegistry
    ) -> list[ProviderLoadResult]:
        """Load all non-default providers from env and TOML.

        Args:
            default_provider: The default provider name (to skip when loading).
            registry: ProviderRegistry to register loaded configs.

        Returns:
            List of ProviderLoadResult objects for each provider loaded.
        """
        results = []
        loaded_providers = set()

        # First: Discover providers from TOML configuration
        try:
            loader = self._get_alias_config_loader()
            config = loader.load_config()
            toml_providers = config.get("providers", {})

            for provider_name, provider_config in toml_providers.items():
                # Skip if this is the default provider (already loaded)
                if provider_name == default_provider:
                    continue

                # Load provider if:
                # 1. It has OAuth auth-mode (no API key needed)
                # 2. It has an api-key in TOML config
                # 3. It has a PROVIDER_API_KEY env var
                auth_mode = provider_config.get("auth-mode", "").lower()
                has_toml_api_key = bool(provider_config.get("api-key"))
                has_env_api_key = bool(os.environ.get(f"{provider_name.upper()}_API_KEY"))

                if auth_mode in ("oauth", "passthrough") or has_toml_api_key or has_env_api_key:
                    result = self._load_provider_config_with_result(provider_name, registry)
                    if result is not None:
                        results.append(result)
                        loaded_providers.add(provider_name)
        except ImportError as e:
            self._logger.warning(
                f"TOML configuration loading not available: {e}. "
                "Only environment variables will be used for provider discovery."
            )
        except OSError as e:
            self._logger.error(
                f"Cannot read TOML configuration files: {e}. Check file permissions and paths."
            )
        except Exception as e:
            self._logger.error(
                f"Failed to load TOML configuration: {e}. "
                "Falling back to environment variable scanning."
            )

        # Second: Scan environment for any additional providers (backward compatibility)
        for env_key, _env_value in os.environ.items():
            if env_key.endswith("_API_KEY") and not env_key.startswith("CUSTOM_"):
                provider_name = self._normalize_provider_name(env_key[:-8])
                # Skip if this is the default provider or already loaded from TOML
                if provider_name == default_provider or provider_name in loaded_providers:
                    continue
                result = self._load_provider_config_with_result(provider_name, registry)
                if result is not None:
                    results.append(result)

        return results

    def _load_provider_config_with_result(
        self,
        provider_name: str,
        registry: "Any",  # ProviderRegistry
    ) -> ProviderLoadResult | None:
        """Load a single provider with error handling and tracking.

        Args:
            provider_name: The name of the provider (lowercase).
            registry: ProviderRegistry to register the config.

        Returns:
            ProviderLoadResult if provider was found, None if skipped.
        """
        provider_upper = provider_name.upper()
        toml_config = self.load_toml_config(provider_name)

        # Detect auth mode
        auth_mode = self._detect_auth_mode(provider_name, toml_config)

        # For OAuth mode, we don't require an API key
        if auth_mode == AuthMode.OAUTH:
            raw_api_key = ""  # OAuth uses tokens, not API keys
        else:
            raw_api_key = os.environ.get(f"{provider_upper}_API_KEY") or toml_config.get(
                "api-key", ""
            )
            if not raw_api_key:
                # Skip entirely if no API key and not OAuth mode
                return None

        # Support multiple static keys
        if auth_mode != AuthMode.OAUTH:
            api_keys = raw_api_key.split()
            if len(api_keys) == 0:
                return None
            if len(api_keys) > 1 and PASSTHROUGH_SENTINEL in api_keys:
                raise ValueError(
                    f"Provider '{provider_name}' has mixed configuration: "
                    f"'!PASSTHRU' cannot be combined with static keys"
                )
            api_key = api_keys[0]
        else:
            # OAuth mode: no API key needed, use empty string as placeholder
            api_key = ""
            api_keys = None

        # Load base URL with precedence: env > TOML > default
        base_url = os.environ.get(f"{provider_upper}_BASE_URL") or toml_config.get("base-url")
        if not base_url:
            # Create result for partial configuration (missing base URL)
            return ProviderLoadResult(
                name=provider_name,
                status="partial",
                message=(
                    f"Missing {provider_upper}_BASE_URL (configure in environment or "
                    "vandamme-config.toml)"
                ),
                api_key_hash=self._get_api_key_hash(api_key),
                base_url=None,
            )

        # Load other settings with precedence: env > TOML > defaults
        api_format = os.environ.get(
            f"{provider_upper}_API_FORMAT", toml_config.get("api-format", "openai")
        )
        if api_format not in ["openai", "anthropic"]:
            api_format = "openai"  # Default to openai if invalid

        # Get defaults section for fallback
        defaults_section = self._get_alias_config_loader().get_defaults()

        # Load timeout and max-retries with fallback chain
        timeout = self._get_config_with_fallback(
            toml_config=toml_config,
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section=defaults_section,
            provider_name=provider_name,
        )
        max_retries = self._get_config_with_fallback(
            toml_config=toml_config,
            key="max-retries",
            env_var="MAX_RETRIES",
            defaults_section=defaults_section,
            provider_name=provider_name,
        )

        # Create result for successful configuration
        result = ProviderLoadResult(
            name=provider_name,
            status="success",
            api_key_hash=self._get_api_key_hash(api_key),
            base_url=base_url,
        )

        # Create the config with auth_mode properly set
        config = ProviderConfig(
            name=provider_name,
            api_key=api_key,
            api_keys=api_keys if api_keys is not None and len(api_keys) > 1 else None,
            base_url=base_url,
            api_version=os.environ.get(f"{provider_upper}_API_VERSION")
            or toml_config.get("api-version"),
            timeout=timeout,
            max_retries=max_retries,
            custom_headers=self.get_custom_headers(provider_upper),
            api_format=api_format,
            tool_name_sanitization=bool(toml_config.get("tool-name-sanitization", False)),
            auth_mode=auth_mode,
            models_url=os.environ.get(f"{provider_upper}_MODELS_URL")
            or toml_config.get("models-url"),
        )

        # Register to provider registry
        registry.register(config)

        return result
