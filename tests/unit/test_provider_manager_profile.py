"""Unit tests for ProviderManager profile integration."""

import pytest

from src.core.provider_config import ProviderConfig
from src.core.provider_manager import ProviderManager


@pytest.mark.unit
class TestProviderManagerProfileIntegration:
    """Test cases for ProviderManager profile methods."""

    def test_profile_manager_attribute(self):
        """Test that ProviderManager can accept ProfileManager."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        provider_mgr = ProviderManager(profile_manager=profile_mgr)

        assert provider_mgr.profile_manager is profile_mgr

    def test_get_effective_timeout_with_profile(self):
        """Test get_effective_timeout uses profile value."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {"test": {"timeout": 150, "max-retries": 5, "aliases": {}, "source": "test"}}
        )

        provider_mgr = ProviderManager(profile_manager=profile_mgr)
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,  # Base config has 90
            max_retries=2,
        )
        provider_mgr._registry.register(config)

        profile = profile_mgr.get_profile("test")
        timeout = provider_mgr.get_effective_timeout("openai", profile)

        # Profile timeout (150) should override base config (90)
        assert timeout == 150

    def test_get_effective_timeout_without_profile(self):
        """Test get_effective_timeout uses base config when no profile."""
        provider_mgr = ProviderManager()
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,
            max_retries=2,
        )
        provider_mgr._registry.register(config)

        timeout = provider_mgr.get_effective_timeout("openai", None)
        assert timeout == 90

    def test_get_effective_timeout_profile_none_inherits(self):
        """Test get_effective_timeout when profile.timeout is None."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {"inherit": {"timeout": None, "max-retries": 5, "aliases": {}, "source": "test"}}
        )

        provider_mgr = ProviderManager(profile_manager=profile_mgr)
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,
            max_retries=2,
        )
        provider_mgr._registry.register(config)

        profile = profile_mgr.get_profile("inherit")
        timeout = provider_mgr.get_effective_timeout("openai", profile)

        # Profile timeout is None, should use base config
        assert timeout == 90

    def test_get_effective_max_retries_with_profile(self):
        """Test get_effective_max_retries uses profile value."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {"test": {"timeout": 90, "max-retries": 7, "aliases": {}, "source": "test"}}
        )

        provider_mgr = ProviderManager(profile_manager=profile_mgr)
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,
            max_retries=2,  # Base config has 2
        )
        provider_mgr._registry.register(config)

        profile = profile_mgr.get_profile("test")
        retries = provider_mgr.get_effective_max_retries("openai", profile)

        # Profile max_retries (7) should override base config (2)
        assert retries == 7

    def test_get_effective_max_retries_without_profile(self):
        """Test get_effective_max_retries uses base config when no profile."""
        provider_mgr = ProviderManager()
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,
            max_retries=2,
        )
        provider_mgr._registry.register(config)

        retries = provider_mgr.get_effective_max_retries("openai", None)
        assert retries == 2

    def test_get_effective_max_retries_profile_none_inherits(self):
        """Test get_effective_max_retries when profile.max_retries is None."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {"inherit": {"timeout": 120, "max-retries": None, "aliases": {}, "source": "test"}}
        )

        provider_mgr = ProviderManager(profile_manager=profile_mgr)
        config = ProviderConfig(
            name="openai",
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=90,
            max_retries=2,
        )
        provider_mgr._registry.register(config)

        profile = profile_mgr.get_profile("inherit")
        retries = provider_mgr.get_effective_max_retries("openai", profile)

        # Profile max_retries is None, should use base config
        assert retries == 2

    def test_get_effective_unknown_provider(self):
        """Test get_effective methods return None for unknown provider."""
        from src.core.profile_manager import ProfileManager

        profile_mgr = ProfileManager()
        provider_mgr = ProviderManager(profile_manager=profile_mgr)

        # Unknown provider, no profile
        timeout = provider_mgr.get_effective_timeout("unknown", None)
        assert timeout is None

        retries = provider_mgr.get_effective_max_retries("unknown", None)
        assert retries is None
