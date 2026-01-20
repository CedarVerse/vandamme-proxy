"""Unit tests for profile_config module."""

import pytest

from src.core.profile_config import ProfileConfig


@pytest.mark.unit
class TestProfileConfig:
    """Test cases for ProfileConfig."""

    def test_profile_config_creation_valid(self):
        """Test creating a valid profile configuration."""
        profile = ProfileConfig(
            name="webdev-good",
            timeout=105,
            max_retries=4,
            aliases={"haiku": "zai:haiku", "sonnet": "poe:gpt-5.1-codex-mini"},
            source="local",
        )
        assert profile.name == "webdev-good"
        assert profile.timeout == 105
        assert profile.max_retries == 4
        assert profile.aliases["haiku"] == "zai:haiku"
        assert profile.source == "local"

    def test_validate_with_all_valid_provider_prefixes(self):
        """Test validation passes when all aliases have provider prefixes."""
        profile = ProfileConfig(
            name="test",
            timeout=60,
            max_retries=2,
            aliases={
                "haiku": "openai:gpt-4o-mini",
                "sonnet": "anthropic:claude-3-5-sonnet-20241022",
                "opus": "poe:gpt-5.2",
            },
            source="test",
        )
        available_providers = {"openai", "anthropic", "poe"}
        errors = profile.validate(available_providers)
        assert errors == []

    def test_validate_fails_missing_provider_prefix(self):
        """Test validation fails when alias lacks provider prefix."""
        profile = ProfileConfig(
            name="invalid",
            timeout=60,
            max_retries=2,
            aliases={"haiku": "gpt-4o-mini"},  # Missing "openai:" prefix
            source="test",
        )
        available_providers = {"openai", "anthropic"}
        errors = profile.validate(available_providers)
        assert len(errors) == 1
        assert "must include provider prefix" in errors[0]
        assert 'Invalid: haiku = "gpt-4o-mini"' in errors[0]
        assert 'Valid: haiku = "provider:model"' in errors[0]

    def test_validate_fails_unknown_provider(self):
        """Test validation fails when alias references unknown provider."""
        profile = ProfileConfig(
            name="invalid",
            timeout=60,
            max_retries=2,
            aliases={"haiku": "unknown-provider:model"},
            source="test",
        )
        available_providers = {"openai", "anthropic", "poe"}
        errors = profile.validate(available_providers)
        assert len(errors) == 1
        assert "references unknown provider 'unknown-provider'" in errors[0]
        assert "Available providers:" in errors[0]

    def test_validate_multiple_errors(self):
        """Test validation returns multiple errors."""
        profile = ProfileConfig(
            name="invalid",
            timeout=60,
            max_retries=2,
            aliases={"bad1": "no-prefix", "bad2": "unknown:model"},
            source="test",
        )
        available_providers = {"openai"}
        errors = profile.validate(available_providers)
        assert len(errors) == 2

    def test_timeout_none_allows_inheritance(self):
        """Test that None timeout means inherit from defaults."""
        profile = ProfileConfig(
            name="inherit-test", timeout=None, max_retries=4, aliases={}, source="test"
        )
        assert profile.timeout is None

    def test_max_retries_none_allows_inheritance(self):
        """Test that None max_retries means inherit from defaults."""
        profile = ProfileConfig(
            name="inherit-test", timeout=90, max_retries=None, aliases={}, source="test"
        )
        assert profile.max_retries is None
