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
            mock_pm.default_target = "openai"
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
            mock_pm.default_target = "openai"
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
            mock_pm.default_target = "openai"
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
            mock_pm.default_target = "openai"
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

    # ------------------------------------------------------------------
    # Regression tests: default profile resolution for bare model names
    # ------------------------------------------------------------------

    def test_bare_model_resolves_via_default_profile_aliases(self):
        """Bare model names should resolve through the default profile's aliases.

        When VDM_DEFAULT_TARGET is set to a profile name (e.g. "top"), bare
        model requests (no prefix) must look up aliases in that profile *before*
        falling back to AliasManager or the default provider.

        This exercises the code path in ModelManager.resolve_model() at
        lines ~80-91 where ``default_profile`` is checked for bare models.
        """
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            # default_target always returns a *real* provider (backward compat)
            mock_pm.default_target = "openai"
            # default_profile returns the profile name when the configured
            # default is a profile rather than a real provider.
            mock_pm.default_profile = "top"
            mock_pm.parse_model_name.side_effect = lambda m: (
                m.split(":", 1) if ":" in m else ("openai", m)
            )
            mock_pm_class.return_value = mock_pm

            # Profile "top" has an alias: opus -> opencodego:kimi-k2.6
            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {
                    "top": {
                        "timeout": None,
                        "max-retries": None,
                        "aliases": {"opus": "opencodego:kimi-k2.6"},
                        "source": "test",
                    }
                }
            )
            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # Bare "opus" should resolve via the default profile's alias
            provider, model = model_manager.resolve_model("opus")
            assert provider == "opencodego"
            assert model == "kimi-k2.6"

    def test_bare_model_falls_through_when_profile_has_no_matching_alias(self):
        """Bare model names with no matching profile alias should fall through.

        When the default target is a profile but the model name is not found in
        that profile's alias map, resolution must proceed to AliasManager (or
        the default provider if no AliasManager is configured).
        """
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_target = "openai"
            mock_pm.default_profile = "top"
            mock_pm.parse_model_name.side_effect = lambda m: (
                m.split(":", 1) if ":" in m else ("openai", m)
            )
            mock_pm_class.return_value = mock_pm

            # Profile "top" only has an alias for "opus", nothing else
            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {
                    "top": {
                        "timeout": None,
                        "max-retries": None,
                        "aliases": {"opus": "opencodego:kimi-k2.6"},
                        "source": "test",
                    }
                }
            )
            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            # No alias manager -> fall through to default provider directly
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # "haiku" is NOT in the profile's aliases -> pass through unchanged
            provider, model = model_manager.resolve_model("haiku")
            assert provider == "openai"
            assert model == "haiku"

    def test_bare_model_uses_alias_manager_when_default_is_provider(self):
        """When default target is a real provider, bare names use AliasManager.

        If ``default_profile`` is None (the default target is a provider, not a
        profile), the profile-alias code path must be skipped entirely and
        AliasManager should handle resolution as before.
        """
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_target = "openai"
            # default_profile is None -> default target is a real provider
            mock_pm.default_profile = None
            mock_pm.parse_model_name.side_effect = lambda m: (
                m.split(":", 1) if ":" in m else ("openai", m)
            )
            mock_pm_class.return_value = mock_pm

            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles({})
            mock_pm.profile_manager = profile_mgr

            # Mock AliasManager that resolves "sonnet" -> "anthropic:claude-3-5-sonnet"
            mock_alias_manager = MagicMock()
            mock_alias_manager.has_aliases.return_value = True
            mock_alias_manager.resolve_alias.return_value = "anthropic:claude-3-5-sonnet"

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = mock_alias_manager

            model_manager = ModelManager(mock_config)

            provider, model = model_manager.resolve_model("sonnet")
            # AliasManager resolved it; parse_model_name split the provider prefix
            assert provider == "anthropic"
            assert model == "claude-3-5-sonnet"

    def test_profile_provider_name_collision(self):
        """Profile wins when profile and provider share the same name.

        When both a profile and a provider are named "openai", and the default
        target is set to "openai", bare model names must resolve through the
        *profile's* aliases.  This verifies that profile resolution takes
        precedence over provider resolution even in the implicit (default target)
        case, not just for explicit ``profile:model`` prefixes.
        """
        with patch("src.core.provider_manager.ProviderManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.default_target = "openai"
            # The configured default "openai" is detected as a profile
            mock_pm.default_profile = "openai"
            mock_pm.parse_model_name.side_effect = lambda m: (
                m.split(":", 1) if ":" in m else ("openai", m)
            )
            mock_pm_class.return_value = mock_pm

            # Profile named "openai" collides with the provider name
            from src.core.profile_manager import ProfileManager

            profile_mgr = ProfileManager()
            profile_mgr.load_profiles(
                {
                    "openai": {
                        "timeout": 120,
                        "max-retries": 5,
                        "aliases": {"haiku": "anthropic:claude-3-5-haiku-20241022"},
                        "source": "test",
                    }
                }
            )
            mock_pm.profile_manager = profile_mgr

            mock_config = MagicMock()
            mock_config.provider_manager = mock_pm
            mock_config.alias_manager = None

            model_manager = ModelManager(mock_config)

            # Bare "haiku" resolves via profile "openai" alias, NOT the provider
            provider, model = model_manager.resolve_model("haiku")
            assert provider == "anthropic"
            assert model == "claude-3-5-haiku-20241022"

    def test_default_target_still_returns_provider(self):
        """default_target must always be a real provider name.

        Even when the configured default is a profile, ``ProviderManager``
        (via ``DefaultProviderSelector``) must guarantee that
        ``default_target`` returns a usable provider.  ``default_profile``
        returns the profile name separately.
        """
        from src.core.profile_manager import ProfileManager
        from src.core.provider import DefaultProviderSelector

        # Set up a profile named "top" but NOT as a real provider
        profile_mgr = ProfileManager()
        profile_mgr.load_profiles(
            {
                "top": {
                    "timeout": None,
                    "max-retries": None,
                    "aliases": {},
                    "source": "test",
                }
            }
        )

        selector = DefaultProviderSelector(
            default_provider="top",
            source="env",
            profile_manager=profile_mgr,
        )

        # Simulate provider discovery: only "openai" is available
        result = selector.select({"openai": MagicMock()})

        # default_target (actual_default) must be a real provider
        assert result == "openai"
        assert selector.actual_default == "openai"

        # default_profile must be set to the profile name
        assert selector.default_profile == "top"

        # configured_default preserves the original user setting
        assert selector.configured_default == "top"
