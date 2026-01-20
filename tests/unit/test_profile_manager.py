"""Unit tests for profile_manager module."""

import pytest

from src.core.profile_manager import ProfileManager


@pytest.mark.unit
class TestProfileManager:
    """Test cases for ProfileManager."""

    def test_load_profiles_empty_dict(self):
        """Test loading empty profiles dict."""
        manager = ProfileManager()
        manager.load_profiles({})
        assert manager.list_profiles() == []
        assert manager.get_profile("nonexistent") is None

    def test_load_profiles_single_profile(self):
        """Test loading a single profile."""
        manager = ProfileManager()
        profiles_dict = {
            "webdev-good": {
                "timeout": 105,
                "max-retries": 4,
                "aliases": {"haiku": "zai:haiku"},
                "source": "local",
            }
        }
        manager.load_profiles(profiles_dict)

        assert manager.list_profiles() == ["webdev-good"]
        profile = manager.get_profile("webdev-good")
        assert profile is not None
        assert profile.name == "webdev-good"
        assert profile.timeout == 105
        assert profile.max_retries == 4
        assert profile.aliases == {"haiku": "zai:haiku"}

    def test_load_profiles_multiple(self):
        """Test loading multiple profiles."""
        manager = ProfileManager()
        profiles_dict = {
            "webdev-good": {"timeout": 105, "max-retries": 4, "aliases": {}, "source": "local"},
            "coding-fast": {"timeout": 60, "max-retries": 1, "aliases": {}, "source": "user"},
            "research-deep": {"timeout": 180, "max-retries": 5, "aliases": {}, "source": "package"},
        }
        manager.load_profiles(profiles_dict)

        assert set(manager.list_profiles()) == {"webdev-good", "coding-fast", "research-deep"}
        assert manager.get_profile("coding-fast").timeout == 60

    def test_load_profiles_clears_previous(self):
        """Test that loading profiles clears previous ones."""
        manager = ProfileManager()
        manager.load_profiles(
            {"old": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"}}
        )
        assert manager.list_profiles() == ["old"]

        manager.load_profiles(
            {"new": {"timeout": 120, "max-retries": 3, "aliases": {}, "source": "test"}}
        )
        assert manager.list_profiles() == ["new"]
        assert manager.get_profile("old") is None

    def test_get_profile_case_insensitive(self):
        """Test that get_profile is case-insensitive."""
        manager = ProfileManager()
        profiles_dict = {
            "WebDev-Good": {"timeout": 105, "max-retries": 4, "aliases": {}, "source": "test"}
        }
        manager.load_profiles(profiles_dict)

        # All these should return the same profile
        profile1 = manager.get_profile("WebDev-Good")
        profile2 = manager.get_profile("webdev-good")
        profile3 = manager.get_profile("WEBDEV-GOOD")

        assert profile1 is not None
        assert profile1 is profile2
        assert profile1 is profile3

    def test_is_profile(self):
        """Test is_profile method."""
        manager = ProfileManager()
        manager.load_profiles(
            {"test-profile": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"}}
        )

        assert manager.is_profile("test-profile")
        assert manager.is_profile("TEST-PROFILE")  # Case insensitive
        assert not manager.is_profile("nonexistent")
        assert not manager.is_profile("")

    def test_validate_all(self):
        """Test validate_all returns errors for invalid profiles."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "valid-profile": {
                    "timeout": 90,
                    "max-retries": 2,
                    "aliases": {"haiku": "openai:gpt-4o-mini"},
                    "source": "test",
                },
                "invalid-prefix": {
                    "timeout": 90,
                    "max-retries": 2,
                    "aliases": {"haiku": "no-prefix"},
                    "source": "test",
                },
                "invalid-provider": {
                    "timeout": 90,
                    "max-retries": 2,
                    "aliases": {"haiku": "unknown:model"},
                    "source": "test",
                },
            }
        )

        available_providers = {"openai", "anthropic"}
        errors = manager.validate_all(available_providers)

        assert "valid-profile" in errors
        assert errors["valid-profile"] == []

        assert "invalid-prefix" in errors
        assert len(errors["invalid-prefix"]) == 1

        assert "invalid-provider" in errors
        assert len(errors["invalid-provider"]) == 1

    def test_list_profiles_sorted(self):
        """Test that list_profiles returns sorted names."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "zebra": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
                "alpha": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
                "beta": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
            }
        )

        assert manager.list_profiles() == ["alpha", "beta", "zebra"]

    def test_detect_collisions_no_collisions(self):
        """Test collision detection with no overlapping names."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "webdev": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
                "fast": {"timeout": 60, "max-retries": 1, "aliases": {}, "source": "test"},
            }
        )

        providers = {"openai", "anthropic", "poe"}
        collisions = manager.detect_collisions(providers)

        assert collisions == []

    def test_detect_collisions_single_collision(self):
        """Test collision detection with one overlapping name."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "openai": {"timeout": 120, "max-retries": 3, "aliases": {}, "source": "test"},
                "webdev": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
            }
        )

        providers = {"openai", "anthropic", "poe"}
        collisions = manager.detect_collisions(providers)

        assert len(collisions) == 1
        assert "openai" in collisions[0]
        assert "takes precedence" in collisions[0]

    def test_detect_collisions_multiple_collisions(self):
        """Test collision detection with multiple overlapping names."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "openai": {"timeout": 120, "max-retries": 3, "aliases": {}, "source": "test"},
                "anthropic": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
                "webdev": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"},
            }
        )

        providers = {"openai", "anthropic", "poe"}
        collisions = manager.detect_collisions(providers)

        assert len(collisions) == 2

    def test_detect_collisions_case_insensitive(self):
        """Test collision detection is case-insensitive."""
        manager = ProfileManager()
        manager.load_profiles(
            {
                "OpenAI": {"timeout": 120, "max-retries": 3, "aliases": {}, "source": "test"},
            }
        )

        providers = {"openai", "anthropic"}
        collisions = manager.detect_collisions(providers)

        assert len(collisions) == 1

    def test_reload_profiles(self):
        """Test profile reload functionality."""
        manager = ProfileManager()
        # Load initial profiles
        manager.load_profiles(
            {"initial": {"timeout": 90, "max-retries": 2, "aliases": {}, "source": "test"}}
        )
        assert manager.list_profiles() == ["initial"]

        # Reload with new profiles
        manager.reload_profiles(
            {"reloaded": {"timeout": 120, "max-retries": 3, "aliases": {}, "source": "test"}}
        )
        assert manager.list_profiles() == ["reloaded"]
        assert manager.get_profile("initial") is None
