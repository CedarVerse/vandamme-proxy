"""Tests for AliasResolverCache class.

This test module validates the caching behavior for alias resolution,
including hit/miss tracking, TTL expiration, generation-based invalidation,
and max size eviction.
"""

import time

import pytest

from src.core.alias_manager import AliasResolverCache


class TestAliasResolverCache:
    """Test suite for AliasResolverCache functionality."""

    def test_cache_put_and_get(self) -> None:
        """Test basic cache put and get operations."""
        cache = AliasResolverCache(ttl_seconds=300.0, max_size=100)

        # Put a value
        cache.put("test-key", "resolved-model")
        assert cache.get_stats()["size"] == 1

        # Get the value
        result = cache.get("test-key")
        assert result == "resolved-model"

    def test_cache_miss_returns_none(self) -> None:
        """Test that cache miss returns None."""
        cache = AliasResolverCache()

        result = cache.get("nonexistent-key")
        assert result is None

    def test_cache_hit_tracking(self) -> None:
        """Test that cache hits are tracked correctly."""
        cache = AliasResolverCache()
        cache.put("key", "value")

        # First access is a hit
        cache.get("key")
        assert cache._hits == 1
        assert cache._misses == 0

        # Second access is also a hit
        cache.get("key")
        assert cache._hits == 2
        assert cache._misses == 0

    def test_cache_miss_tracking(self) -> None:
        """Test that cache misses are tracked correctly."""
        cache = AliasResolverCache()

        # Miss for nonexistent key
        cache.get("nonexistent")
        assert cache._hits == 0
        assert cache._misses == 1

        # Another miss
        cache.get("another-nonexistent")
        assert cache._hits == 0
        assert cache._misses == 2

    def test_cache_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        cache = AliasResolverCache()
        cache.put("key", "value")

        # 2 hits, 1 miss = 66.67%
        cache.get("key")
        cache.get("key")
        cache.get("nonexistent")

        assert 0.66 < cache.hit_rate < 0.67

    def test_cache_hit_rate_empty(self) -> None:
        """Test hit rate is 0 when cache is empty."""
        cache = AliasResolverCache()
        assert cache.hit_rate == 0.0

    def test_ttl_expiration(self) -> None:
        """Test that cache entries expire after TTL."""
        cache = AliasResolverCache(ttl_seconds=0.1)  # 100ms TTL

        # Put a value
        cache.put("key", "value")
        assert cache.get("key") == "value"

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        result = cache.get("key")
        assert result is None

    def test_generation_based_invalidation(self) -> None:
        """Test that generation change invalidates all entries."""
        cache = AliasResolverCache(ttl_seconds=300.0)

        # Put some values
        cache.put("key1", "value1")
        cache.put("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

        # Invalidate cache (increment generation)
        cache.invalidate()

        # All entries should be invalidated
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache._generation == 1

    def test_clear_cache(self) -> None:
        """Test clearing the cache."""
        cache = AliasResolverCache()

        # Put some values
        cache.put("key1", "value1")
        cache.put("key2", "value2")

        # Generate some hits and misses
        cache.get("key1")
        cache.get("nonexistent")

        assert cache.get_stats()["size"] == 2
        assert cache._hits == 1
        assert cache._misses == 1

        # Clear cache
        cache.clear()

        # Everything should be reset
        assert cache.get_stats()["size"] == 0
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._generation == 0

    def test_max_size_eviction(self) -> None:
        """Test that oldest entry is evicted when max size is reached."""
        cache = AliasResolverCache(ttl_seconds=300.0, max_size=3)

        # Fill the cache to max capacity
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        assert cache.get_stats()["size"] == 3

        # Add one more - should evict oldest
        cache.put("key4", "value4")

        assert cache.get_stats()["size"] == 3
        assert cache.get("key1") is None  # Oldest evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_max_size_eviction_oldest_first(self) -> None:
        """Test that eviction is based on timestamp (oldest first)."""
        cache = AliasResolverCache(ttl_seconds=300.0, max_size=2)

        cache.put("key1", "value1")
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        cache.put("key2", "value2")

        # Both should be present
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

        # Add third - key1 should be evicted (oldest)
        cache.put("key3", "value3")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_cache_stats(self) -> None:
        """Test that get_stats returns correct information."""
        cache = AliasResolverCache(ttl_seconds=300.0, max_size=100)

        cache.put("key1", "value1")
        cache.put("key2", "value2")

        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.get_stats()

        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "66.67%"
        assert stats["generation"] == 0

    def test_put_overwrites_existing(self) -> None:
        """Test that put overwrites existing entry."""
        cache = AliasResolverCache()

        cache.put("key", "value1")
        assert cache.get("key") == "value1"

        cache.put("key", "value2")
        assert cache.get("key") == "value2"

        # Size should still be 1
        assert cache.get_stats()["size"] == 1

    def test_multiple_invalidations(self) -> None:
        """Test multiple cache invalidations."""
        cache = AliasResolverCache()

        cache.put("key", "value")
        assert cache.get("key") == "value"

        # First invalidation
        cache.invalidate()
        assert cache._generation == 1
        assert cache.get("key") is None

        # Add new value and invalidate again
        cache.put("key", "value2")
        cache.invalidate()
        assert cache._generation == 2

    def test_cache_key_types(self) -> None:
        """Test cache with different key formats."""
        cache = AliasResolverCache()

        # Provider-scoped key format
        cache.put("openai:model", "openai:gpt-4")
        assert cache.get("openai:model") == "openai:gpt-4"

        # Simple key format
        cache.put("simple", "result")
        assert cache.get("simple") == "result"

        # Key with provider prefix (empty provider)
        cache.put(":model", "resolved")
        assert cache.get(":model") == "resolved"

    @pytest.mark.unit
    def test_cache_with_zero_ttl(self) -> None:
        """Test cache behavior with zero TTL (entries expire immediately)."""
        cache = AliasResolverCache(ttl_seconds=0.0)

        cache.put("key", "value")

        # With zero TTL, entries expire immediately
        result = cache.get("key")
        assert result is None

    @pytest.mark.unit
    def test_cache_with_large_ttl(self) -> None:
        """Test cache behavior with very large TTL."""
        cache = AliasResolverCache(ttl_seconds=86400)  # 24 hours

        cache.put("key", "value")

        # Should still be valid
        result = cache.get("key")
        assert result == "value"

    @pytest.mark.unit
    def test_cache_hit_rate_formatting(self) -> None:
        """Test that hit rate is formatted as percentage."""
        cache = AliasResolverCache()

        cache.put("key", "value")

        # 50% hit rate
        cache.get("key")  # hit
        cache.get("miss")  # miss

        stats = cache.get_stats()
        assert "%" in stats["hit_rate"]
        assert stats["hit_rate"] == "50.00%"
