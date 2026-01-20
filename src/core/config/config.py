"""Configuration singleton for Vandamme Proxy.

This module provides a simple, elegant singleton that gives direct
access to configuration values without unnecessary abstraction.

Configuration is organized into focused modules:
- server: Server settings (host, port, log level)
- providers: Provider configuration (default provider, API keys)
- security: Authentication settings (proxy API key, custom headers)
- timeouts: Connection settings (timeouts, retries, streaming)
- cache: Cache configuration (models cache, alias cache)
- metrics: Metrics and monitoring (token limits, SSE settings)
- middleware: Middleware configuration (thought signatures)
- top_models: Top models feature configuration

The Config class implements the ConfigProvider protocol from src.core.protocols,
enabling clean dependency inversion and eliminating circular imports.
"""

import hashlib
import os
from typing import TYPE_CHECKING

from src.core.config.cache import CacheSettings
from src.core.config.metrics import MetricsSettings
from src.core.config.middleware import MiddlewareSettings
from src.core.config.provider_utils import get_default_base_url, get_provider_base_url_env_var
from src.core.config.providers import ProviderSettings
from src.core.config.security import SecuritySettings
from src.core.config.server import ServerSettings
from src.core.config.timeouts import TimeoutSettings
from src.core.config.top_models import TopModelsSettings

if TYPE_CHECKING:
    from src.api.services.alias_service import AliasService
    from src.core.alias_manager import AliasManager
    from src.core.provider_manager import ProviderManager


class Config:
    """Configuration singleton with direct access to all settings.

    This class provides direct property access to configuration values
    by delegating to the appropriate configuration module. All configuration
    values are loaded at initialization time from environment variables
    using schema-based validation.

    The Config class implements the ConfigProvider protocol for dependency
    inversion. Manager properties delegate to the global singletons managed
    by src.core.dependencies.

    This design ensures:
    1. No circular imports - protocols break dependency cycles
    2. Clean initialization order - all dependencies initialized explicitly
    3. Testability - protocols can be mocked easily
    """

    def __init__(self) -> None:
        # Load all configuration modules at startup
        self._server = ServerSettings.load()
        self._providers = ProviderSettings.load()
        self._security = SecuritySettings.load()
        self._timeouts = TimeoutSettings.load()
        self._cache = CacheSettings.load()
        self._metrics = MetricsSettings.load()
        self._middleware = MiddlewareSettings.load()
        self._top_models = TopModelsSettings.load()

    # Server settings
    @property
    def host(self) -> str:
        return self._server.host

    @property
    def port(self) -> int:
        return self._server.port

    @property
    def log_level(self) -> str:
        return self._server.log_level

    @property
    def strict_profile_validation(self) -> bool:
        return self._server.strict_profile_validation

    # Provider settings
    @property
    def default_provider(self) -> str:
        return self._providers.default_provider

    @property
    def default_provider_source(self) -> str:
        return self._providers.default_provider_source

    @property
    def openai_api_key(self) -> str | None:
        return self._providers.default_provider_api_key

    @property
    def base_url(self) -> str:
        base_url_env_var = get_provider_base_url_env_var(self.default_provider)
        return os.environ.get(base_url_env_var, get_default_base_url(self.default_provider))

    @property
    def azure_api_version(self) -> str | None:
        return os.environ.get("AZURE_API_VERSION")

    # Security settings
    @property
    def proxy_api_key(self) -> str | None:
        return self._security.proxy_api_key

    def validate_client_api_key(self, client_api_key: str) -> bool:
        return SecuritySettings.validate_client_api_key(self.proxy_api_key, client_api_key)

    def get_custom_headers(self) -> dict[str, str]:
        return SecuritySettings.get_custom_headers()

    # Timeout settings
    @property
    def request_timeout(self) -> int:
        return self._timeouts.request_timeout

    @property
    def streaming_read_timeout(self) -> float | None:
        return self._timeouts.streaming_read_timeout

    @property
    def streaming_connect_timeout(self) -> float:
        return self._timeouts.streaming_connect_timeout

    @property
    def max_retries(self) -> int:
        return self._timeouts.max_retries

    # Metrics settings
    @property
    def log_request_metrics(self) -> bool:
        return self._metrics.log_request_metrics

    @property
    def max_tokens_limit(self) -> int:
        return self._metrics.max_tokens_limit

    @property
    def min_tokens_limit(self) -> int:
        return self._metrics.min_tokens_limit

    @property
    def active_requests_sse_enabled(self) -> bool:
        return self._metrics.active_requests_sse_enabled

    @property
    def active_requests_sse_interval(self) -> float:
        return self._metrics.active_requests_sse_interval

    @property
    def active_requests_sse_heartbeat(self) -> float:
        return self._metrics.active_requests_sse_heartbeat

    # Cache settings
    @property
    def cache_dir(self) -> str:
        return self._cache.cache_dir

    @property
    def models_cache_enabled(self) -> bool:
        return self._cache.models_cache_enabled

    @property
    def models_cache_ttl_hours(self) -> int:
        return self._cache.models_cache_ttl_hours

    @property
    def alias_cache_ttl_seconds(self) -> float:
        return self._cache.alias_cache_ttl_seconds

    @property
    def alias_cache_max_size(self) -> int:
        return self._cache.alias_cache_max_size

    @property
    def alias_max_chain_length(self) -> int:
        return self._cache.alias_max_chain_length

    # Middleware settings
    @property
    def gemini_thought_signatures_enabled(self) -> bool:
        return self._middleware.gemini_thought_signatures_enabled

    @property
    def thought_signature_cache_ttl(self) -> float:
        return self._middleware.thought_signature_cache_ttl

    @property
    def thought_signature_max_cache_size(self) -> int:
        return self._middleware.thought_signature_max_cache_size

    @property
    def thought_signature_cleanup_interval(self) -> float:
        return self._middleware.thought_signature_cleanup_interval

    # Top models settings
    @property
    def top_models_source(self) -> str:
        return self._top_models.source

    @property
    def top_models_rankings_file(self) -> str:
        return self._top_models.rankings_file

    @property
    def top_models_timeout_seconds(self) -> float:
        return self._top_models.timeout_seconds

    @property
    def top_models_exclude(self) -> tuple[str, ...]:
        return self._top_models.exclude

    # Manager properties - delegate to global singletons from dependencies module
    # These properties provide backward compatibility while using centralized initialization
    @property
    def provider_manager(self) -> "ProviderManager":
        """Get the global ProviderManager instance.

        Delegates to src.core.dependencies for centralized singleton management.
        This ensures clean initialization order and eliminates circular imports.
        """
        from src.core.dependencies import get_provider_manager

        return get_provider_manager()

    @property
    def alias_manager(self) -> "AliasManager":
        """Get the global AliasManager instance.

        Delegates to src.core.dependencies for centralized singleton management.
        This ensures clean initialization order and eliminates circular imports.
        """
        from src.core.dependencies import get_alias_manager

        return get_alias_manager()

    @property
    def alias_service(self) -> "AliasService":
        """Get the global AliasService instance.

        Delegates to src.core.dependencies for centralized singleton management.
        This ensures clean initialization order and eliminates circular imports.
        """
        from src.core.dependencies import get_alias_service

        return get_alias_service()

    # Utility methods
    def validate_api_key(self) -> bool:
        if not self.openai_api_key:
            return False
        return self.openai_api_key.startswith("sk-")

    @property
    def api_key_hash(self) -> str:
        return (
            "<not-set>"
            if not self.openai_api_key
            else "sha256:" + hashlib.sha256(self.openai_api_key.encode()).hexdigest()[:16] + "..."
        )
