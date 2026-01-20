"""
Model alias management for provider-specific <PROVIDER>_ALIAS_* environment variables.

This module provides flexible model name resolution with case-insensitive
substring matching, where aliases are scoped to specific providers.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from time import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.alias.resolver import AliasResolverChain

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    """Immutable cache entry for alias resolution results.

    Attributes:
        resolved_model: The resolved model name
        timestamp: Unix timestamp when cached
        generation: Cache generation for invalidation
    """

    resolved_model: str
    timestamp: float
    generation: int


@dataclass(frozen=True)
class CacheStats:
    """Statistics for alias resolution cache.

    Attributes:
        size: Current number of entries
        max_size: Maximum capacity
        hits: Number of cache hits
        misses: Number of cache misses
        hit_rate: Hit rate as formatted string (e.g., "85.50%")
        generation: Current cache generation
    """

    size: int
    max_size: int
    hits: int
    misses: int
    hit_rate: str
    generation: int


@dataclass
class AliasResolverCache:
    """TTL cache for alias resolution with generation-based invalidation.

    Cache entries are invalidated when:
    - TTL expires (default: 5 minutes)
    - Generation counter increments (aliases are reloaded)

    Attributes:
        ttl_seconds: Time-to-live for cache entries in seconds
        max_size: Maximum number of entries in the cache
        _cache: Internal cache storage mapping keys to entries
        _generation: Current generation for cache invalidation
        _hits: Number of cache hits
        _misses: Number of cache misses
    """

    ttl_seconds: float = 300.0  # 5 minutes default
    max_size: int = 1000
    _cache: dict[str, CacheEntry] = field(default_factory=dict)
    _generation: int = 0
    _hits: int = 0
    _misses: int = 0

    def get(self, key: str) -> str | None:
        """Get cached value if valid.

        Args:
            key: Cache key (typically "provider:model" or "model")

        Returns:
            Cached resolved model name, or None if not cached/expired/invalidated
        """
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        # Check generation (cache invalidation on reload)
        if entry.generation != self._generation:
            self._cache.pop(key, None)
            self._misses += 1
            return None

        # Check TTL
        if time() - entry.timestamp > self.ttl_seconds:
            self._cache.pop(key, None)
            self._misses += 1
            return None

        self._hits += 1
        return entry.resolved_model

    def put(self, key: str, value: str) -> None:
        """Cache a value with current timestamp and generation.

        Args:
            key: Cache key
            value: Resolved model name to cache
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
            self._cache.pop(oldest_key, None)

        self._cache[key] = CacheEntry(
            resolved_model=value, timestamp=time(), generation=self._generation
        )

    def invalidate(self) -> None:
        """Increment generation to invalidate all cache entries.

        Call this when aliases are reloaded at runtime.
        """
        self._generation += 1
        logger.info(f"[AliasCache] Invalidated all entries (generation={self._generation})")

    def clear(self) -> None:
        """Clear all cache entries and reset stats."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._generation = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate.

        Returns:
            Hit rate as a float between 0.0 and 1.0
        """
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> CacheStats:
        """Get cache statistics for monitoring.

        Returns:
            CacheStats with cache metrics: size, max_size, hits, misses, hit_rate, generation
        """
        return CacheStats(
            size=len(self._cache),
            max_size=self.max_size,
            hits=self._hits,
            misses=self._misses,
            hit_rate=f"{self.hit_rate:.2%}",
            generation=self._generation,
        )


class AliasManager:
    """
    Manages model aliases with case-insensitive substring matching.

    Supports provider-specific <PROVIDER>_ALIAS_* environment variables where:
    - POE_ALIAS_HAIKU=grok-4.1-fast-non-reasoning
    - OPENAI_ALIAS_FAST=gpt-4o-mini
    - ANTHROPIC_ALIAS_CHAT=claude-3-5-sonnet-20241022
    """

    def __init__(
        self,
        cache_ttl_seconds: float = 300.0,
        cache_max_size: int = 1000,
        _resolver_chain: Any = None,
    ) -> None:
        """Initialize AliasManager with caching support.

        Args:
            cache_ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
            cache_max_size: Maximum number of cached entries (default: 1000)
            _resolver_chain: Optional custom resolver chain (for testing/internal use)
        """
        self.aliases: dict[str, dict[str, str]] = {}  # {provider: {alias_name: target_model}}
        self._fallback_aliases: dict[str, dict[str, str]] = {}  # Cached fallback config
        self._defaults_aliases: dict[str, str] = {}  # Global defaults.aliases from TOML
        self._default_provider: str | None = None  # Lazily loaded
        self._loaded: bool = False  # Track whether loading has occurred

        # Initialize cache
        self._cache = AliasResolverCache(ttl_seconds=cache_ttl_seconds, max_size=cache_max_size)

        # Store resolver chain (will be initialized after aliases are loaded)
        self._resolver_chain = _resolver_chain

        # Load fallback aliases first
        self._load_fallback_aliases()

        # Then load environment variable aliases (these take precedence)
        self._load_aliases()

        # Merge fallback aliases for any missing configurations
        self._merge_fallback_aliases()

        # Initialize default resolver chain if not provided
        if self._resolver_chain is None:
            self._resolver_chain = self._create_default_resolver_chain()

    def _load_aliases(self) -> None:
        """
        Load provider-specific <PROVIDER>_ALIAS_* environment variables.

        Expected format: <PROVIDER>_ALIAS_<NAME>=<target_model>
        Example: POE_ALIAS_HAIKU=grok-4.1-fast-non-reasoning
        """
        alias_pattern = re.compile(r"^(.+)_ALIAS_(.+)$")
        loaded_count = 0
        skipped_count = 0

        # Get default provider (lazily, without triggering ProviderManager init)
        from src.core.alias_config import AliasConfigLoader

        loader = AliasConfigLoader()
        defaults = loader.get_defaults()
        self._default_provider = defaults.get("default-provider", "openai")

        # NOTE: Intentionally do NOT call ProviderManager.load_provider_configs() here.
        # This allows AliasManager to be instantiated without requiring provider API keys.
        # Provider validation is done lazily when aliases are actually resolved.
        # In unit tests, ProviderManager is patched to provide mock _configs.

        for env_key, env_value in os.environ.items():
            match = alias_pattern.match(env_key)
            if match:
                provider, alias_name = match.groups()
                provider = provider.lower()
                alias_name = alias_name.lower()  # Store aliases in lowercase

                if not env_value or not env_value.strip():
                    logger.warning(f"Empty alias value for {env_key}, skipping")
                    skipped_count += 1
                    continue

                if self._validate_alias(alias_name, env_value):
                    # Initialize provider dict if needed
                    if provider not in self.aliases:
                        self.aliases[provider] = {}

                    self.aliases[provider][alias_name] = env_value.strip()
                    loaded_count += 1
                    logger.debug(f"Loaded model alias: {provider}:{alias_name} -> {env_value}")
                else:
                    logger.warning(
                        f"Invalid alias configuration for {env_key}={env_value}, skipping"
                    )
                    skipped_count += 1

        if self.aliases:
            total_aliases = sum(len(aliases) for aliases in self.aliases.values())
            logger.info(
                f"Loaded {total_aliases} explicit model aliases from {len(self.aliases)} providers "
                f"({skipped_count} skipped)"
            )

    def _validate_alias(self, alias: str, value: str) -> bool:
        """
        Validate alias configuration.

        Args:
            alias: The alias name (lowercase)
            value: The alias target value

        Returns:
            True if valid, False otherwise
        """
        # Check for circular reference
        if alias == value.lower():
            logger.error(f"Circular alias reference detected: {alias} -> {value}")
            return False

        # Basic format validation - allow most characters in model names
        # Allow provider:model format or plain model names
        # Be permissive since model names can have various formats
        if not value or not value.strip():
            return False

        # Disallow characters that are clearly invalid for model names
        # Allow letters, numbers, hyphens, underscores, dots, slashes, colons
        # @ is not allowed as it's typically used for usernames or emails
        if "@" in value:
            logger.warning(f"Invalid alias target format (contains @): {value}")
            return False

        return True

    def _load_fallback_aliases(self) -> None:
        """Load fallback aliases from TOML configuration files.

        Loads both provider-specific aliases from [provider.aliases] sections
        and global fallback aliases from [defaults.aliases] section.
        """
        try:
            from src.core.alias_config import AliasConfigLoader

            loader = AliasConfigLoader()
            config = loader.load_config()
            providers_config = config.get("providers", {})

            # Extract aliases from provider configurations
            fallback_aliases = {}
            for provider_name, provider_config in providers_config.items():
                if isinstance(provider_config, dict) and "aliases" in provider_config:
                    aliases = provider_config["aliases"]
                    if isinstance(aliases, dict):
                        fallback_aliases[provider_name] = aliases

            self._fallback_aliases = fallback_aliases

            # Load global defaults.aliases
            self._defaults_aliases = loader.get_defaults_aliases()

            if self._fallback_aliases:
                total_fallback = sum(len(aliases) for aliases in self._fallback_aliases.values())
                logger.debug(f"Loaded {total_fallback} fallback aliases from configuration")
            if self._defaults_aliases:
                logger.debug(
                    f"Loaded {len(self._defaults_aliases)} global default aliases "
                    f"from [defaults.aliases]"
                )
        except ImportError as e:
            logger.debug(f"Could not import AliasConfigLoader: {e}")
            self._fallback_aliases = {}
            self._defaults_aliases = {}
        except Exception as e:
            # Check if this is a TOML decode error (tomli raises Exception subclass)
            error_type = type(e).__name__
            if "TOMLDecodeError" in error_type or "DecodeError" in error_type:
                logger.error(f"Invalid TOML in fallback config: {e}")
                raise  # Fail fast for config errors - this is a critical error
            elif "FileNotFoundError" in error_type or "NotFoundError" in error_type:
                logger.debug("No fallback config file found, using empty fallbacks")
                self._fallback_aliases = {}
                self._defaults_aliases = {}
            else:
                logger.warning(f"Failed to load fallback aliases: {e}")
                self._fallback_aliases = {}
                self._defaults_aliases = {}

    def _merge_fallback_aliases(self) -> None:
        """Merge fallback aliases for any missing configurations.

        IMPORTANT: We load fallback aliases for all providers defined in config
        to support AliasManager initialization without API keys. Filtering to
        active providers happens at display time (get_all_aliases, _print_alias_summary).
        """
        # Get available providers for validation.
        #
        # IMPORTANT: Alias management must not require provider API keys.
        # Unit tests (and many offline workflows) intentionally run without any
        # *_API_KEY env vars. We therefore consider a provider "known" if it is
        # present in configuration defaults, config files, or env var *names*.
        from src.core.alias_config import AliasConfigLoader

        loader = AliasConfigLoader()
        config = loader.load_config()

        configured_providers = set((config.get("providers") or {}).keys())
        env_providers = {
            env_key[:-8].lower()
            for env_key in os.environ
            if env_key.endswith("_API_KEY") and not env_key.startswith("CUSTOM_")
        }
        available_providers = configured_providers | env_providers

        # Note: "default-provider" is a preference, not proof that a provider is enabled.
        # We intentionally do not treat it as "configured" for alias scoping.

        for provider, fallback_aliases in self._fallback_aliases.items():
            # Only apply fallbacks for configured providers
            if provider not in available_providers:
                logger.debug(f"Skipping fallback aliases for unconfigured provider '{provider}'")
                continue

            # Initialize provider dict if needed
            if provider not in self.aliases:
                self.aliases[provider] = {}

            # Add fallback aliases that weren't explicitly configured
            for alias, target in fallback_aliases.items():
                if alias not in self.aliases[provider]:
                    self.aliases[provider][alias] = target
                    logger.debug(f"Applied fallback alias: {provider}:{alias} -> {target}")

        # Apply global defaults.aliases to all configured providers
        # These have the lowest priority: env var > provider fallback > defaults.aliases
        if self._defaults_aliases:
            for provider in available_providers:
                # Initialize provider dict if needed
                if provider not in self.aliases:
                    self.aliases[provider] = {}

                # Add default aliases that weren't explicitly configured or in provider fallback
                for alias, target in self._defaults_aliases.items():
                    if alias not in self.aliases[provider]:
                        self.aliases[provider][alias] = target
                        logger.debug(
                            f"Applied global default alias: {provider}:{alias} -> {target}"
                        )

    def resolve_alias(self, model: str, provider: str | None = None) -> str | None:
        """
        Resolve model name to alias value using the resolver chain with caching.

        Resolution algorithm:
        1. Check cache for cached result
        2. If cache miss, use resolver chain for full resolution
        3. Cache the result for future lookups

        Args:
            model: The requested model name
            provider: Optional provider name to scope the search. If None, searches
                     across all providers (backward compatible behavior).

        Returns:
            The resolved alias target with provider prefix (e.g., "poe:grok-4.1-fast")
            or None if no match found
        """
        if not model:
            logger.debug("No model name provided, cannot resolve alias")
            return None

        # Build cache key
        cache_key = f"{provider or ''}:{model}" if provider else model

        # Check cache first (skip for literal prefix which bypasses resolution)
        if not model.startswith("!"):
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"[AliasCache] HIT for '{model}' -> '{cached_result}'")
                return cached_result
            logger.debug(f"[AliasCache] MISS for '{model}', performing resolution")
        else:
            logger.debug(f"[AliasCache] SKIP for literal '{model}', bypassing cache")

        # Early return if no aliases configured
        if not self.aliases:
            logger.debug("No aliases configured, returning None")
            return None

        # Import here to avoid circular dependency
        from src.core.alias.resolver import ResolutionContext

        # Build resolution context
        context = ResolutionContext(
            model=model,
            provider=provider,
            default_provider=self._default_provider or "openai",
            aliases=self.aliases,
        )

        # Resolve through the resolver chain
        result = self._resolver_chain.resolve(context)

        # If no alias was found, return None
        if not result.was_resolved:
            logger.debug(f"No alias matched model name '{model}'")
            return None

        resolved_model: str = result.resolved_model

        # Log chain resolution if applicable
        if result.resolution_path:
            logger.info(
                f"[AliasManager] Resolved '{model}' through chain: "
                f"{' -> '.join(result.resolution_path)} -> '{resolved_model}'"
            )

        # Cache the result before returning (only for non-literal resolutions)
        if not model.startswith("!"):
            self._cache.put(cache_key, resolved_model)
            logger.debug(
                f"[AliasCache] Cached result for '{model}' -> '{resolved_model}', "
                f"stats: {self._cache.get_stats()}"
            )

        return resolved_model

    def get_all_aliases(self) -> dict[str, dict[str, str]]:
        """
        Get all configured aliases grouped by provider.

        Returns:
            Dictionary of {provider: {alias_name: target_model}}
        """
        return {provider: aliases.copy() for provider, aliases in self.aliases.items()}

    def get_explicit_aliases(self) -> dict[str, dict[str, str]]:
        """
        Get only explicitly configured aliases (excluding fallbacks).

        Returns:
            Dictionary of {provider: {alias_name: target_model}}
        """
        explicit_aliases = {}

        for provider, aliases in self.aliases.items():
            provider_explicit = {}
            fallback_aliases = self._fallback_aliases.get(provider, {})

            for alias, target in aliases.items():
                # Include only if not from fallback or explicitly overridden
                if alias not in fallback_aliases or target != fallback_aliases[alias]:
                    provider_explicit[alias] = target

            if provider_explicit:
                explicit_aliases[provider] = provider_explicit

        return explicit_aliases

    def has_aliases(self) -> bool:
        """
        Check if any aliases are configured.

        Returns:
            True if aliases exist, False otherwise
        """
        return bool(self.aliases)

    def get_alias_count(self) -> int:
        """
        Get the number of configured aliases.

        Returns:
            Number of aliases across all providers
        """
        return sum(len(aliases) for aliases in self.aliases.values())

    def get_fallback_aliases(self) -> dict[str, dict[str, str]]:
        """Get fallback aliases loaded from TOML configuration.

        Returns:
            Copy of fallback aliases dict to prevent external mutation.
            Maps provider name to their fallback alias definitions.
        """
        return {p: aliases.copy() for p, aliases in self._fallback_aliases.items()}

    def invalidate_cache(self) -> None:
        """Invalidate the alias resolution cache.

        Call this when aliases are reloaded at runtime.
        """
        self._cache.invalidate()

    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics for monitoring.

        Returns:
            CacheStats with cache metrics: size, max_size, hits, misses, hit_rate, generation
        """
        return self._cache.get_stats()

    def _create_default_resolver_chain(self) -> "AliasResolverChain":
        """Create the default resolver chain for alias resolution.

        Imports are done here to avoid circular dependencies.
        The chain order is: LiteralPrefix -> ChainedAlias -> SubstringMatcher -> MatchRanker
        """
        from src.core.alias.resolver import (
            AliasResolverChain,
            ChainedAliasResolver,
            LiteralPrefixResolver,
            MatchRanker,
            SubstringMatcher,
        )

        return AliasResolverChain(
            [
                LiteralPrefixResolver(),
                ChainedAliasResolver(),
                SubstringMatcher(),
                MatchRanker(),
            ]
        )
