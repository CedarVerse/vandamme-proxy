"""Lazy initialization for provider and alias managers.

This module provides lazy initialization logic without requiring
the full Config facade. The managers are initialized on first access
to avoid circular dependencies.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.services.alias_service import AliasService
    from src.core.alias_manager import AliasManager
    from src.core.provider_manager import ProviderManager


class LazyManagers:
    """Lazy initialization for manager singletons.

    This class defers expensive initialization until first access,
    preventing circular dependencies between config and managers.
    """

    def __init__(self) -> None:
        self._provider_manager: ProviderManager | None = None
        self._alias_manager: AliasManager | None = None
        self._alias_service: AliasService | None = None

    @property
    def provider_manager(self) -> "ProviderManager":
        """Get or create the provider manager.

        The provider manager is initialized with a MiddlewareConfig DTO
        passed via dependency injection to avoid circular dependencies.

        Returns:
            The ProviderManager instance
        """
        if self._provider_manager is None:
            from src.core.config.middleware import MiddlewareConfig, MiddlewareSettings
            from src.core.config.providers import ProviderSettings
            from src.core.provider_manager import ProviderManager

            provider_config = ProviderSettings.load()
            middleware_config = MiddlewareSettings.load()

            # Create middleware config DTO to pass via dependency injection
            middleware_dto = MiddlewareConfig(
                gemini_thought_signatures_enabled=middleware_config.gemini_thought_signatures_enabled,
                thought_signature_max_cache_size=middleware_config.thought_signature_max_cache_size,
                thought_signature_cache_ttl=middleware_config.thought_signature_cache_ttl,
                thought_signature_cleanup_interval=middleware_config.thought_signature_cleanup_interval,
            )

            self._provider_manager = ProviderManager(
                default_provider=provider_config.default_provider,
                default_provider_source=provider_config.default_provider_source,
                middleware_config=middleware_dto,
            )
            self._provider_manager.load_provider_configs()

        return self._provider_manager

    @property
    def alias_manager(self) -> "AliasManager":
        """Get or create the alias manager.

        The alias manager is initialized with cache configuration
        from the CacheSettings.

        Returns:
            The AliasManager instance
        """
        if self._alias_manager is None:
            from src.core.alias_manager import AliasManager
            from src.core.config.cache import CacheSettings

            cache_config = CacheSettings.load()
            self._alias_manager = AliasManager(
                cache_ttl_seconds=cache_config.alias_cache_ttl_seconds,
                cache_max_size=cache_config.alias_cache_max_size,
            )

        return self._alias_manager

    @property
    def alias_service(self) -> "AliasService":
        """Get or create the alias service.

        The alias service coordinates AliasManager and ProviderManager
        to provide aliases filtered to active providers only.

        Returns:
            The AliasService instance
        """
        if self._alias_service is None:
            from src.api.services.alias_service import AliasService

            self._alias_service = AliasService(
                alias_manager=self.alias_manager,
                provider_manager=self.provider_manager,
            )

        return self._alias_service
