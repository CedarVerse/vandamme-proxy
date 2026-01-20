"""Unit tests for profile section parsing in AliasConfigLoader."""

import tempfile
from pathlib import Path

import pytest

from src.core.alias_config import AliasConfigLoader


@pytest.mark.unit
class TestAliasConfigProfileParsing:
    """Test cases for profile section parsing."""

    def test_parse_profile_sections_with_hash_prefix(self):
        """Test parsing profile sections with # prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "vandamme-config.toml"
            config_path.write_text(
                """
["#webdev-good"]
timeout = 105
max-retries = 4

["#webdev-good".aliases]
haiku = "zai:haiku"
sonnet = "poe:gpt-5.1-codex-mini"

["#coding-fast"]
timeout = 60
max-retries = 1

["#coding-fast".aliases]
haiku = "openai:gpt-5.1-mini"

[openai]
base-url = "https://api.openai.com/v1"

[openai.aliases]
fast = "gpt-4o"

[defaults]
default-provider = "openai"
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            # Override config paths for testing
            loader._config_paths = [config_path]
            loader.reset_cache()
            config = loader.load_config()

            # Check profiles were parsed
            assert "profiles" in config
            profiles = config["profiles"]

            assert "webdev-good" in profiles  # # prefix stripped
            assert profiles["webdev-good"]["timeout"] == 105
            assert profiles["webdev-good"]["max-retries"] == 4
            assert profiles["webdev-good"]["aliases"]["haiku"] == "zai:haiku"
            assert profiles["webdev-good"]["aliases"]["sonnet"] == "poe:gpt-5.1-codex-mini"

            assert "coding-fast" in profiles
            assert profiles["coding-fast"]["timeout"] == 60

            # Check providers still work
            assert "providers" in config
            assert "openai" in config["providers"]

    def test_profile_with_no_aliases(self):
        """Test profile without aliases section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
["#simple"]
timeout = 120
max-retries = 3

[defaults]
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()
            config = loader.load_config()

            assert "simple" in config["profiles"]
            assert config["profiles"]["simple"]["timeout"] == 120
            assert config["profiles"]["simple"]["aliases"] == {}

    def test_profile_aliases_lowercase(self):
        """Test that profile aliases are stored lowercase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
["#test".aliases]
Haiku = "openai:gpt-4o-mini"
SONNET = "anthropic:claude-3-5-sonnet-20241022"

[defaults]
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()
            config = loader.load_config()

            aliases = config["profiles"]["test"]["aliases"]
            assert "haiku" in aliases
            assert "sonnet" in aliases
            assert aliases["haiku"] == "openai:gpt-4o-mini"

    def test_profile_inherits_from_defaults(self):
        """Test that profile can omit timeout/max-retries to inherit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
["#inherit"]
# No timeout or max-retries defined

["#inherit".aliases]
haiku = "openai:gpt-4o-mini"

[defaults]
timeout = 100
max-retries = 5
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()
            config = loader.load_config()

            # Profile should have None for unset values (inherit later)
            profile = config["profiles"]["inherit"]
            assert "timeout" not in profile or profile.get("timeout") is None
            assert "max-retries" not in profile or profile.get("max-retries") is None
