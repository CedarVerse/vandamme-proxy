"""Unit tests for ProfileManager initialization in dependencies."""

import pytest

from src.core.dependencies import get_profile_manager
from src.core.profile_manager import ProfileManager
from src.core.provider_manager import ProviderManager


@pytest.mark.unit
class TestDependenciesProfileManager:
    """Test cases for ProfileManager initialization."""

    def test_profile_manager_attribute(self):
        """Test that ProviderManager can accept ProfileManager."""
        profile_mgr = ProfileManager()
        provider_mgr = ProviderManager(profile_manager=profile_mgr)

        assert provider_mgr.profile_manager is profile_mgr

    def test_get_effective_timeout_with_profile(self):
        """Test get_effective_timeout uses profile value."""
        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {"test": {"timeout": 150, "max-retries": 5, "aliases": {}, "source": "test"}}
        )

        provider_mgr = ProviderManager(profile_manager=profile_mgr)

        # Use registry instead of _configs
        from src.core.provider_config import ProviderConfig

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

    def test_get_profile_manager_raises_without_init(self):
        """Test that get_profile_manager raises RuntimeError if not initialized."""
        # Reset the module-level variable
        from src.core import dependencies

        dependencies._profile_manager = None

        with pytest.raises(RuntimeError, match="ProfileManager not initialized"):
            get_profile_manager()
