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
default-target = "openai"
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

    def test_parse_profiles_section_new_syntax(self):
        """Test parsing profile sections with new [profiles.name] syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "vandamme-config.toml"
            config_path.write_text(
                """
[profiles.webdev-good]
timeout = 105
max-retries = 4

[profiles.webdev-good.aliases]
haiku = "zai:haiku"
sonnet = "poe:gpt-5.1-codex-mini"

[profiles.coding-fast]
timeout = 60
max-retries = 1

[profiles.coding-fast.aliases]
haiku = "openai:gpt-5.1-mini"

[openai]
base-url = "https://api.openai.com/v1"

[openai.aliases]
fast = "gpt-4o"

[defaults]
default-target = "openai"
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

            assert "webdev-good" in profiles
            assert profiles["webdev-good"]["timeout"] == 105
            assert profiles["webdev-good"]["max-retries"] == 4
            assert profiles["webdev-good"]["aliases"]["haiku"] == "zai:haiku"
            assert profiles["webdev-good"]["aliases"]["sonnet"] == "poe:gpt-5.1-codex-mini"

            assert "coding-fast" in profiles
            assert profiles["coding-fast"]["timeout"] == 60

            # Check providers still work
            assert "providers" in config
            assert "openai" in config["providers"]

    def test_parse_legacy_profile_with_deprecation_warning(self, caplog):
        """Test that legacy ["#name"] syntax emits deprecation warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
["#legacy"]
timeout = 120
max-retries = 3

["#legacy".aliases]
haiku = "openai:gpt-4o-mini"

[defaults]
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()

            with caplog.at_level("WARNING"):
                config = loader.load_config()

            # Verify profile was parsed
            assert "legacy" in config["profiles"]
            assert config["profiles"]["legacy"]["timeout"] == 120

            # Verify deprecation warning was emitted
            assert any("Deprecated TOML syntax" in record.message for record in caplog.records), (
                "Expected deprecation warning for legacy syntax"
            )

    def test_both_syntaxes_new_wins(self):
        """Test that new [profiles.name] syntax takes precedence when both exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
[profiles.test]
timeout = 100
max-retries = 5

[profiles.test.aliases]
haiku = "new-syntax:model"
sonnet = "new-syntax:sonnet"

["#test"]
timeout = 50
max-retries = 1

["#test".aliases]
haiku = "old-syntax:model"
opus = "old-syntax:opus"

[defaults]
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()
            config = loader.load_config()

            # Should use new syntax values
            profile = config["profiles"]["test"]
            assert profile["timeout"] == 100  # From new syntax
            assert profile["max-retries"] == 5  # From new syntax
            assert profile["aliases"]["haiku"] == "new-syntax:model"
            assert profile["aliases"]["sonnet"] == "new-syntax:sonnet"
            # Old syntax opus should NOT be present because new syntax was found
            assert "opus" not in profile["aliases"]

    def test_both_syntaxes_across_files(self):
        """Test precedence when new and legacy syntax are in different config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Package defaults with legacy syntax
            defaults_path = Path(tmpdir) / "defaults.toml"
            defaults_path.write_text(
                """
["#shared"]
timeout = 80
max-retries = 2

["#shared".aliases]
haiku = "defaults:haiku"

[defaults]
timeout = 90
"""
            )

            # Local override with new syntax (higher priority)
            local_path = Path(tmpdir) / "vandamme-config.toml"
            local_path.write_text(
                """
[profiles.shared]
timeout = 120
max-retries = 5

[profiles.shared.aliases]
haiku = "local:haiku"
sonnet = "local:sonnet"
"""
            )

            loader = AliasConfigLoader()
            # Order matters: reversed, so defaults is processed first, then local
            loader._config_paths = [local_path, defaults_path]
            loader.reset_cache()
            config = loader.load_config()

            # Local (new syntax) should win due to file priority order
            profile = config["profiles"]["shared"]
            assert profile["timeout"] == 120
            assert profile["max-retries"] == 5
            assert profile["aliases"]["haiku"] == "local:haiku"

    def test_deprecation_warning_once_per_profile(self, caplog):
        """Test that deprecation warning is emitted only once per profile name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
["#test"]
timeout = 100

["#test".aliases]
haiku = "model1"

[defaults]
timeout = 90
"""
            )

            loader = AliasConfigLoader()
            loader._config_paths = [config_path]
            loader.reset_cache()

            with caplog.at_level("WARNING"):
                # Load multiple times
                loader.load_config()
                loader.load_config(force_reload=True)

            # Should only warn once per profile name
            deprecation_warnings = [
                record for record in caplog.records if "Deprecated TOML syntax" in record.message
            ]
            assert len(deprecation_warnings) == 1, "Expected only one deprecation warning"

    def test_new_syntax_with_no_aliases(self):
        """Test new syntax profile without aliases section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
[profiles.simple]
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

    def test_new_syntax_aliases_lowercase(self):
        """Test that new syntax profile aliases are stored lowercase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
[profiles.test.aliases]
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

    def test_new_syntax_inherits_from_defaults(self):
        """Test that new syntax profile can omit timeout/max-retries to inherit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.toml"
            config_path.write_text(
                """
[profiles.inherit]
# No timeout or max-retries defined

[profiles.inherit.aliases]
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
