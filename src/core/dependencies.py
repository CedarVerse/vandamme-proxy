"""Application dependency setup.

This module provides centralized initialization of all application singletons.
It replaces lazy loading patterns with explicit initialization at startup,
eliminating circular imports and hidden dependencies.

All dependencies are created once at startup in a controlled order,
ensuring clean initialization without circular dependencies.

Usage:
    from src.core.dependencies import initialize_app, get_config, get_provider_manager

    # Call once at application startup
    initialize_app()

    # Access dependencies throughout the application
    config = get_config()
    provider_manager = get_provider_manager()
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.services.alias_service import AliasService
    from src.core.alias_manager import AliasManager
    from src.core.config import Config
    from src.core.model_manager import ModelManager
    from src.core.provider_manager import ProviderManager

logger = logging.getLogger(__name__)

# Module-level storage for singleton instances
# These are initialized once by initialize_app() and accessed via getters
_config: "Config | None" = None
_provider_manager: "ProviderManager | None" = None
_alias_manager: "AliasManager | None" = None
_model_manager: "ModelManager | None" = None
_alias_service: "AliasService | None" = None


def initialize_app() -> None:
    """Initialize all application dependencies in correct order.

    This function must be called once at application startup (typically
    in src/main.py) before any other code accesses the dependencies.

    Initialization order:
    1. Config - loads all configuration settings
    2. ProviderManager - creates provider clients using config
    3. AliasManager - loads model aliases (independent of providers)
    4. ModelManager - orchestrates model resolution using both managers
    5. AliasService - coordinates AliasManager and ProviderManager

    Raises:
        RuntimeError: If called more than once or if dependencies fail to initialize.
    """
    global _config, _provider_manager, _alias_manager, _model_manager, _alias_service

    # Guard against double initialization
    if _config is not None:
        logger.warning("Dependencies already initialized, skipping")
        return

    logger.info("Initializing application dependencies...")

    # Step 1: Initialize Config (no dependencies)
    from src.core.config import Config

    _config = Config()
    logger.debug("Config initialized")

    # Step 2: Initialize ProviderManager (depends on Config)
    from src.core.config.middleware import MiddlewareConfig
    from src.core.provider_manager import ProviderManager

    # Create middleware config DTO from config
    middleware_dto = MiddlewareConfig(
        gemini_thought_signatures_enabled=_config.gemini_thought_signatures_enabled,
        thought_signature_max_cache_size=_config.thought_signature_max_cache_size,
        thought_signature_cache_ttl=_config.thought_signature_cache_ttl,
        thought_signature_cleanup_interval=_config.thought_signature_cleanup_interval,
    )

    _provider_manager = ProviderManager(
        default_provider=_config.default_provider,
        default_provider_source=_config.default_provider_source,
        middleware_config=middleware_dto,
    )
    _provider_manager.load_provider_configs()
    logger.debug("ProviderManager initialized")

    # Step 3: Initialize AliasManager (no external dependencies)
    from src.core.alias_manager import AliasManager

    _alias_manager = AliasManager(
        cache_ttl_seconds=_config.alias_cache_ttl_seconds,
        cache_max_size=_config.alias_cache_max_size,
    )
    logger.debug("AliasManager initialized")

    # Step 4: Initialize ModelManager (depends on all three above)
    from src.core.model_manager import ModelManager

    _model_manager = ModelManager(config=_config)
    logger.debug("ModelManager initialized")

    # Step 5: Initialize AliasService (depends on AliasManager and ProviderManager)
    from src.api.services.alias_service import AliasService

    _alias_service = AliasService(
        alias_manager=_alias_manager,
        provider_manager=_provider_manager,
    )
    logger.debug("AliasService initialized")

    logger.info("All dependencies initialized successfully")


def get_config() -> "Config":
    """Get the global Config instance.

    Returns:
        The Config singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _config is None:
        raise RuntimeError("Config not initialized. Call initialize_app() first.")
    return _config


def get_provider_manager() -> "ProviderManager":
    """Get the global ProviderManager instance.

    Returns:
        The ProviderManager singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _provider_manager is None:
        raise RuntimeError("ProviderManager not initialized. Call initialize_app() first.")
    return _provider_manager


def get_alias_manager() -> "AliasManager":
    """Get the global AliasManager instance.

    Returns:
        The AliasManager singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _alias_manager is None:
        raise RuntimeError("AliasManager not initialized. Call initialize_app() first.")
    return _alias_manager


def get_model_manager() -> "ModelManager":
    """Get the global ModelManager instance.

    Returns:
        The ModelManager singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _model_manager is None:
        raise RuntimeError("ModelManager not initialized. Call initialize_app() first.")
    return _model_manager


def get_alias_service() -> "AliasService":
    """Get the global AliasService instance.

    Returns:
        The AliasService singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _alias_service is None:
        raise RuntimeError("AliasService not initialized. Call initialize_app() first.")
    return _alias_service
