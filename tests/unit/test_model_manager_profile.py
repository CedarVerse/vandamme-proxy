"""Unit tests for ModelManager profile resolution."""

from unittest.mock import MagicMock, patch

import pytest

from src.core.model_manager import ModelManager
from src.core.profile_config import ProfileConfig


@pytest.mark.unit
class TestModelManagerProfileResolution:
    """Test cases for profile prefix detection and resolution."""

    def test_profile_prefix_detected_before_provider(self):
        """Test that profile prefix is detected before provider."""
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_provider = "openai"
            # Mock parse_model_name to return the input split by ":"
            # This allows us to see what model name was actually passed
            mock_pm.parse_model_name.side_effect = lambda m: (
                m.split(":", 1) if ":" in m else ("openai", m)
            )

            mock_pm_class.return_value = mock_pm

            # Create ProfileManager with a profile
            ProfileConfig(
                name="webdev-good",
                timeout=105,
                max_retries=4,
                aliases={"haiku": "zai:haiku"},
                source="test",
            )

            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {
                    "webdev-good": {
                        "timeout": 105,
                        "max-retries": 4,
                        "aliases": {"haiku": "zai:haiku"},
                        "source": "test",
                    }
                }
            )

            mock_pm.profile_manager = profile_mgr

            # Create mock config
            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # Request with profile prefix
            provider, model = model_manager.resolve_model("webdev-good:haiku")

            # Should use profile's alias (zai:haiku)
            assert provider == "zai"
            assert model == "haiku"

    def test_no_profile_uses_default_provider(self):
        """Test that models without profile prefix use default provider."""
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_provider = "openai"
            mock_pm.parse_model_name.return_value = ("openai", "gpt-4o")

            mock_pm_class.return_value = mock_pm

            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles({})

            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # No profile prefix - should use default provider
            provider, model = model_manager.resolve_model("gpt-4o")
            assert provider == "openai"
            assert model == "gpt-4o"

    def test_provider_prefix_with_profile_manager_present(self):
        """Test direct provider prefix works even with ProfileManager."""
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_provider = "openai"
            mock_pm.parse_model_name.return_value = ("anthropic", "claude-3-5-sonnet-20241022")

            mock_pm_class.return_value = mock_pm

            # ProfileManager exists but doesn't have this name
            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {"webdev-good": {"timeout": 105, "max-retries": 4, "aliases": {}, "source": "test"}}
            )

            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # Direct provider prefix - not a profile
            provider, model = model_manager.resolve_model("anthropic:claude-3-5-sonnet-20241022")
            assert provider == "anthropic"

    def test_profile_takes_precedence_over_same_name_provider(self):
        """Test that profile wins if name matches both profile and provider."""
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_provider = "openai"
            mock_pm.parse_model_name.return_value = ("poe", "gpt-5.1-mini")

            mock_pm_class.return_value = mock_pm

            # Create a profile named "openai" (same as provider)
            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {
                    "openai": {
                        "timeout": 120,
                        "max-retries": 5,
                        "aliases": {"haiku": "poe:gpt-5.1-mini"},
                        "source": "test",
                    }
                }
            )

            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # Profile "openai" should take precedence
            provider, model = model_manager.resolve_model("openai:haiku")
            # Resolved via profile alias: "poe:gpt-5.1-mini"
            # -> parse_model_name splits to poe/gpt-5.1-mini
            assert provider == "poe"
