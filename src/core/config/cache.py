"""Cache configuration module.

This module handles cache-related settings including:
- Models cache configuration
- Alias resolution cache configuration
- Cache directory location

Now uses schema-based loading for automatic type coercion and validation.
"""

from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for cache settings.

    Attributes:
        cache_dir: Directory path for cache storage
        models_cache_enabled: Whether models cache is enabled
        models_cache_ttl_hours: TTL in hours for models cache entries
        alias_cache_ttl_seconds: TTL in seconds for alias cache entries
        alias_cache_max_size: Maximum number of entries in alias cache
        alias_max_chain_length: Maximum steps for alias resolution chain
    """

    cache_dir: str
    models_cache_enabled: bool
    models_cache_ttl_hours: int
    alias_cache_ttl_seconds: float
    alias_cache_max_size: int
    alias_max_chain_length: int


class CacheSettings:
    """Manages cache configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion (str -> int/float/bool)
    - Validation with clear error messages
    - Single source of truth for default values
    - Sophisticated boolean parsing (accepts "true", "1", "yes", "on")
    """

    @staticmethod
    def load() -> CacheConfig:
        """Load cache configuration using schema-based validation.

        Returns:
            CacheConfig with values from environment or defaults

        Raises:
            ConfigError: If any environment variable fails validation
        """
        return CacheConfig(
            cache_dir=load_env_var(ConfigSchema.CACHE_DIR),
            models_cache_enabled=load_env_var(ConfigSchema.MODELS_CACHE_ENABLED),
            models_cache_ttl_hours=load_env_var(ConfigSchema.MODELS_CACHE_TTL_HOURS),
            alias_cache_ttl_seconds=load_env_var(ConfigSchema.ALIAS_CACHE_TTL_SECONDS),
            alias_cache_max_size=load_env_var(ConfigSchema.ALIAS_CACHE_MAX_SIZE),
            alias_max_chain_length=load_env_var(ConfigSchema.ALIAS_MAX_CHAIN_LENGTH),
        )
