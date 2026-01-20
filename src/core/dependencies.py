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

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.api.services.alias_service import AliasService
    from src.core.alias_manager import AliasManager
    from src.core.config import Config
    from src.core.model_manager import ModelManager
    from src.core.profile_manager import ProfileManager
    from src.core.provider_manager import ProviderManager
    from src.core.provider_resolver import ProviderResolver

logger = logging.getLogger(__name__)

# Module-level storage for singleton instances
# These are initialized once by initialize_app() and accessed via getters
_config: "Config | None" = None
_profile_manager: "ProfileManager | None" = None
_provider_manager: "ProviderManager | None" = None
_alias_manager: "AliasManager | None" = None
_model_manager: "ModelManager | None" = None
_alias_service: "AliasService | None" = None
# ProviderResolver initialized after ProfileManager, before ProviderManager
_provider_resolver: "Any" = None  # Will be ProviderResolver

# Lock for thread-safe profile reloading
_profile_reload_lock = asyncio.Lock()


def initialize_app() -> None:
    """Initialize all application dependencies in correct order.

    This function must be called once at application startup (typically
    in src/main.py) before any other code accesses the dependencies.

    Initialization order:
    1. Config - loads all configuration settings
    2. ProfileManager - loads profile configurations from TOML
    3. ProviderManager - creates provider clients using config and profiles
    4. AliasManager - loads model aliases (independent of providers)
    5. ModelManager - orchestrates model resolution using all managers
    6. AliasService - coordinates AliasManager and ProviderManager

    Raises:
        RuntimeError: If called more than once or if dependencies fail to initialize.
    """
    global \
        _config, \
        _profile_manager, \
        _provider_manager, \
        _alias_manager, \
        _model_manager, \
        _alias_service, \
        _provider_resolver

    # Guard against double initialization
    if _config is not None:
        logger.warning("Dependencies already initialized, skipping")
        return

    logger.info("Initializing application dependencies...")

    # Step 1: Initialize Config (no dependencies)
    from src.core.config import Config

    _config = Config()
    logger.debug("Config initialized")

    # Step 2: Initialize ProfileManager (no dependencies)
    from src.core.alias_config import AliasConfigLoader
    from src.core.profile_manager import ProfileManager

    _profile_manager = ProfileManager()
    toml_config = AliasConfigLoader().load_config()
    _profile_manager.load_profiles(toml_config.get("profiles", {}))
    logger.debug("ProfileManager initialized")

    # Step 2.5: Initialize ProviderResolver (depends on ProfileManager)
    from src.core.provider_resolver import ProviderResolver

    _provider_resolver = ProviderResolver(
        default_provider=_config.default_provider,
        profile_manager=_profile_manager,
    )
    logger.debug("ProviderResolver initialized")

    # Step 3: Initialize ProviderManager (depends on Config and ProfileManager)
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
        profile_manager=_profile_manager,  # Pass ProfileManager
        provider_resolver=_provider_resolver,  # Pass ProviderResolver for delegated operations
    )
    _provider_manager.load_provider_configs()
    logger.debug("ProviderManager initialized")

    # Step 4: Initialize AliasManager (no external dependencies)
    from src.core.alias_manager import AliasManager

    _alias_manager = AliasManager(
        cache_ttl_seconds=_config.alias_cache_ttl_seconds,
        cache_max_size=_config.alias_cache_max_size,
    )
    logger.debug("AliasManager initialized")

    # Step 5: Initialize ModelManager (depends on all three above)
    from src.core.model_manager import ModelManager

    _model_manager = ModelManager(config=_config)
    logger.debug("ModelManager initialized")

    # Step 6: Initialize AliasService (depends on AliasManager and ProviderManager)
    from src.api.services.alias_service import AliasService

    _alias_service = AliasService(
        alias_manager=_alias_manager,
        provider_manager=_provider_manager,
    )
    logger.debug("AliasService initialized")

    # Step 7: Validate profiles against available providers
    providers = _provider_manager.list_providers()
    validation_errors = _profile_manager.validate_all(set(providers.keys()))

    # Collect all errors for summary
    all_errors = []
    for profile_name, errors in validation_errors.items():
        if errors:
            for error in errors:
                logger.error(f"Profile validation error [{profile_name}]: {error}")
                all_errors.append(f"[{profile_name}] {error}")

    # Fail fast if strict validation is enabled
    if all_errors and _config.strict_profile_validation:
        raise RuntimeError(
            f"Profile validation failed with {len(all_errors)} error(s). "
            f"Set VDM_STRICT_PROFILE_VALIDATION=false to allow startup with invalid profiles."
        )

    if all_errors:
        logger.warning(
            f"Profile validation encountered {len(all_errors)} error(s) "
            f"but continued due to VDM_STRICT_PROFILE_VALIDATION=false"
        )

    # Step 8: Detect profile-provider name collisions
    collisions = _profile_manager.detect_collisions(set(providers.keys()))
    for collision in collisions:
        logger.info(collision)

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


def get_profile_manager() -> "ProfileManager":
    """Get the global ProfileManager instance.

    Returns:
        The ProfileManager singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _profile_manager is None:
        raise RuntimeError("ProfileManager not initialized. Call initialize_app() first.")
    return _profile_manager


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


def get_provider_resolver() -> "ProviderResolver":
    """Get the global ProviderResolver instance.

    Returns:
        The ProviderResolver singleton.

    Raises:
        RuntimeError: If initialize_app() has not been called.
    """
    if _provider_resolver is None:
        raise RuntimeError("ProviderResolver not initialized. Call initialize_app() first.")
    # Cast needed because _provider_resolver is typed as Any to avoid circular import
    return _provider_resolver  # type: ignore[no-any-return]


async def reload_profiles() -> None:
    """Reload profile configurations from TOML files.

    This function allows hot-reloading profiles without restarting
    the entire application. It uses a lock to ensure thread-safety
    during concurrent requests.

    Raises:
        RuntimeError: If dependencies not initialized or validation fails.
    """
    global _profile_manager

    if _profile_manager is None or _provider_manager is None or _config is None:
        raise RuntimeError("Dependencies not initialized. Call initialize_app() first.")

    from src.core.alias_config import AliasConfigLoader

    # Acquire lock to prevent race conditions with concurrent requests
    async with _profile_reload_lock:
        # Load new profiles first (don't mutate yet)
        toml_config = AliasConfigLoader().load_config(force_reload=True)
        new_profiles_dict = toml_config.get("profiles", {})

        # Validate before applying
        providers = _provider_manager.list_providers()
        validation_errors = _profile_manager.validate_all(set(providers.keys()))

        all_errors = []
        for profile_name, errors in validation_errors.items():
            if errors:
                for error in errors:
                    logger.error(f"Profile validation error [{profile_name}]: {error}")
                    all_errors.append(f"[{profile_name}] {error}")

        if all_errors and _config.strict_profile_validation:
            raise RuntimeError(f"Profile reload validation failed with {len(all_errors)} error(s).")

        # Only apply if validation passed (atomic-ish: clear is fast)
        _profile_manager.reload_profiles(new_profiles_dict)

        # Re-run collision detection
        collisions = _profile_manager.detect_collisions(set(providers.keys()))
        for collision in collisions:
            logger.info(collision)

        logger.info("Profile reload completed successfully")
