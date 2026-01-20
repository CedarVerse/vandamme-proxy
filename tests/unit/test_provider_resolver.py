"""Unit tests for ProviderResolver."""

import pytest

from src.core.provider_resolver import ProviderResolver


@pytest.mark.unit
class TestProviderResolver:
    """Test suite for ProviderResolver class."""

    def test_parse_provider_prefix_with_provider(self) -> None:
        """Test parsing model with provider prefix."""
        resolver = ProviderResolver(default_provider="openai")
        provider, model = resolver.parse_provider_prefix("anthropic:claude-3")
        assert provider == "anthropic"
        assert model == "claude-3"

    def test_parse_provider_prefix_without_provider(self) -> None:
        """Test parsing model without provider prefix."""
        resolver = ProviderResolver(default_provider="openai")
        provider, model = resolver.parse_provider_prefix("gpt-4")
        assert provider is None
        assert model == "gpt-4"

    def test_parse_provider_prefix_case_insensitive(self) -> None:
        """Test that provider names are normalized to lowercase."""
        resolver = ProviderResolver(default_provider="openai")
        provider, model = resolver.parse_provider_prefix("OPENAI:gpt-4")
        assert provider == "openai"
        assert model == "gpt-4"

    def test_parse_provider_prefix_with_colon_in_model(self) -> None:
        """Test parsing when model name contains a colon."""
        resolver = ProviderResolver(default_provider="openai")
        provider, model = resolver.parse_provider_prefix("anthropic:claude:3")
        assert provider == "anthropic"
        assert model == "claude:3"

    def test_resolve_provider_with_prefix(self) -> None:
        """Test resolving provider when model has prefix."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}, "anthropic": {}}
        provider, model = resolver.resolve_provider("anthropic:claude-3", available)
        assert provider == "anthropic"
        assert model == "claude-3"

    def test_resolve_provider_without_prefix(self) -> None:
        """Test resolving provider when model has no prefix."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}, "anthropic": {}}
        provider, model = resolver.resolve_provider("gpt-4", available)
        assert provider == "openai"
        assert model == "gpt-4"

    def test_resolve_provider_not_found(self) -> None:
        """Test that ValueError is raised for unknown provider."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}}
        with pytest.raises(ValueError, match="Provider 'unknown' not found"):
            resolver.resolve_provider("unknown:model", available)

    def test_resolve_provider_not_found_includes_available(self) -> None:
        """Test that error message includes available providers."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}, "anthropic": {}}
        with pytest.raises(ValueError, match="Available providers: anthropic, openai"):
            resolver.resolve_provider("unknown:model", available)

    def test_get_provider_or_default_with_value(self) -> None:
        """Test getting provider name when value is provided."""
        resolver = ProviderResolver(default_provider="openai")
        assert resolver.get_provider_or_default("Anthropic") == "anthropic"

    def test_get_provider_or_default_none(self) -> None:
        """Test getting default provider when value is None."""
        resolver = ProviderResolver(default_provider="openai")
        assert resolver.get_provider_or_default(None) == "openai"

    def test_validate_provider_exists_success(self) -> None:
        """Test validation succeeds when provider exists."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}, "anthropic": {}}
        # Should not raise
        resolver.validate_provider_exists("anthropic", available)

    def test_validate_provider_exists_failure(self) -> None:
        """Test validation fails when provider doesn't exist."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}}
        with pytest.raises(ValueError, match="Provider 'unknown' not found"):
            resolver.validate_provider_exists("unknown", available)

    def test_profile_aware_resolution(self) -> None:
        """Test resolution with profile manager.

        Profiles override aliases but the model part still needs to be resolved.
        When model_part is not in profile aliases, it falls through to normal resolution.
        """
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        # Profile with alias mapping
        profile_mgr.load_profiles(
            {"test-profile": {"aliases": {"haiku": "anthropic:claude-3-5-haiku-20241022"}}}
        )

        resolver = ProviderResolver(
            default_provider="openai",
            profile_manager=profile_mgr,
        )
        available = {"openai": {}, "anthropic": {}}

        # When using profile:model format and model is in profile aliases
        provider, model = resolver.resolve_provider("test-profile:haiku", available)
        # The alias target includes the provider prefix
        assert provider == "anthropic"
        assert model == "claude-3-5-haiku-20241022"

    def test_profile_aware_resolution_without_alias_fallback(self) -> None:
        """Test that non-alias model parts with profile prefix fall through to normal resolution."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        # Profile with no aliases
        profile_mgr.load_profiles({"test-profile": {"aliases": {}}})

        resolver = ProviderResolver(
            default_provider="openai",
            profile_manager=profile_mgr,
        )
        available = {"openai": {}, "anthropic": {}}

        # When model_part is not in profile aliases, it uses default provider
        provider, model = resolver.resolve_provider("test-profile:haiku", available)
        assert provider == "openai"
        assert model == "haiku"

    def test_profile_aware_resolution_no_profile(self) -> None:
        """Test that non-profile names are handled normally."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        profile_mgr.load_profiles({})

        resolver = ProviderResolver(
            default_provider="openai",
            profile_manager=profile_mgr,
        )
        available = {"openai": {}, "anthropic": {}}

        provider, model = resolver.resolve_provider("anthropic:claude-3", available)
        assert provider == "anthropic"
        assert model == "claude-3"

    def test_resolve_provider_empty_string_model(self) -> None:
        """Test resolving with empty string model."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}}
        provider, model = resolver.resolve_provider("", available)
        assert provider == "openai"
        assert model == ""

    def test_resolve_provider_model_with_only_provider(self) -> None:
        """Test resolving model that's just a provider name with colon."""
        resolver = ProviderResolver(default_provider="openai")
        available = {"openai": {}, "anthropic": {}}
        provider, model = resolver.resolve_provider("anthropic:", available)
        assert provider == "anthropic"
        assert model == ""
