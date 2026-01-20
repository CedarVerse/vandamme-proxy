"""Comprehensive tests for [defaults] section fallback functionality.

Tests the fallback chain for:
1. [defaults] timeout and max-retries as provider fallbacks
2. [defaults.aliases] as global alias fallback for all providers
"""

import os
from unittest.mock import patch

import pytest

from src.core.exceptions import ConfigurationError
from src.core.provider_manager import ProviderManager


class TestDefaultsTimeoutMaxRetries:
    """Test [defaults] section fallback for timeout and max-retries."""

    def test_timeout_fallback_to_defaults(self):
        """When provider has no timeout, use defaults.timeout."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com"}},
                "defaults": {"timeout": 60, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {"base-url": "https://test.com"}
            mock_instance.get_defaults.return_value = {"timeout": 60, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.timeout == 60
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_timeout_provider_override(self):
        """Provider timeout takes precedence over defaults.timeout."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com", "timeout": 30}},
                "defaults": {"timeout": 60, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {
                "base-url": "https://test.com",
                "timeout": 30,
            }
            mock_instance.get_defaults.return_value = {"timeout": 60, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.timeout == 30
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_timeout_env_override_all(self):
        """Environment variable overrides all."""
        with (
            patch.dict(os.environ, {"REQUEST_TIMEOUT": "120"}),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com", "timeout": 30}},
                "defaults": {"timeout": 60, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {
                "base-url": "https://test.com",
                "timeout": 30,
            }
            mock_instance.get_defaults.return_value = {"timeout": 60, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.timeout == 120
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_timeout_zero_disables(self):
        """timeout=0 means disable timeout (no wait limit)."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com", "timeout": 0}},
                "defaults": {"timeout": 60, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {
                "base-url": "https://test.com",
                "timeout": 0,
            }
            mock_instance.get_defaults.return_value = {"timeout": 60, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.timeout == 0
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_max_retries_fallback_to_defaults(self):
        """Similar tests for max-retries."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com"}},
                "defaults": {"timeout": 90, "max-retries": 3},
            }
            mock_instance.get_provider_config.return_value = {"base-url": "https://test.com"}
            mock_instance.get_defaults.return_value = {"timeout": 90, "max-retries": 3}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.max_retries == 3
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_max_retries_zero_disables(self):
        """max-retries=0 means no retries (fail immediately)."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com", "max-retries": 0}},
                "defaults": {"timeout": 90, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {
                "base-url": "https://test.com",
                "max-retries": 0,
            }
            mock_instance.get_defaults.return_value = {"timeout": 90, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                manager = ProviderManager(default_provider="testprovider")
                manager.load_provider_configs()
                config = manager.get_provider_config("testprovider")
                assert config.max_retries == 0
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_timeout_not_defined_raises_error(self):
        """timeout not defined anywhere raises ConfigurationError."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com"}},
                "defaults": {},
            }
            mock_instance.get_provider_config.return_value = {"base-url": "https://test.com"}
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    manager = ProviderManager(default_provider="testprovider")
                    manager.load_provider_configs()

                error_msg = str(exc_info.value)
                assert "timeout" in error_msg
                assert "REQUEST_TIMEOUT" in error_msg
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_max_retries_not_defined_raises_error(self):
        """max-retries not defined anywhere raises ConfigurationError."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com"}},
                "defaults": {},
            }
            mock_instance.get_provider_config.return_value = {"base-url": "https://test.com"}
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    manager = ProviderManager(default_provider="testprovider")
                    manager.load_provider_configs()

                error_msg = str(exc_info.value)
                assert "max-retries" in error_msg
                assert "MAX_RETRIES" in error_msg
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)

    def test_negative_timeout_raises_error(self):
        """Negative timeout is invalid."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {"testprovider": {"base-url": "https://test.com", "timeout": -10}},
                "defaults": {"timeout": 90, "max-retries": 2},
            }
            mock_instance.get_provider_config.return_value = {
                "base-url": "https://test.com",
                "timeout": -10,
            }
            mock_instance.get_defaults.return_value = {"timeout": 90, "max-retries": 2}
            mock_instance.get_defaults_aliases.return_value = {}

            os.environ["TESTPROVIDER_API_KEY"] = "test-key"

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    manager = ProviderManager(default_provider="testprovider")
                    manager.load_provider_configs()

                assert "Invalid" in str(exc_info.value)
            finally:
                os.environ.pop("TESTPROVIDER_API_KEY", None)


class TestDefaultsAliases:
    """Test [defaults.aliases] global alias fallback."""

    def test_defaults_alias_fallback(self):
        """When provider has no alias, use defaults.aliases."""
        from src.core.alias_manager import AliasManager

        with (
            patch("src.core.provider_manager.ProviderManager") as mock_pm,
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_pm.return_value._configs = {"poe": {}, "openai": {}}

            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {
                    "poe": {"base-url": "https://test.com"},
                    "openai": {"base-url": "https://openai.com"},
                },
                "defaults": {"aliases": {"haiku": "fallback-model"}},
            }
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {"haiku": "fallback-model"}

            alias_manager = AliasManager()

            aliases = alias_manager.get_all_aliases()
            assert "haiku" in aliases.get("poe", {})
            assert "haiku" in aliases.get("openai", {})
            assert aliases["poe"]["haiku"] == "fallback-model"
            assert aliases["openai"]["haiku"] == "fallback-model"

    def test_provider_alias_override_defaults(self):
        """Provider alias takes precedence over defaults.aliases."""
        from src.core.alias_manager import AliasManager

        with (
            patch("src.core.provider_manager.ProviderManager") as mock_pm,
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_pm.return_value._configs = {"poe": {}, "openai": {}}

            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {
                    "poe": {
                        "base-url": "https://test.com",
                        "aliases": {"haiku": "provider-model"},
                    },
                    "openai": {"base-url": "https://openai.com"},
                },
                "defaults": {"aliases": {"haiku": "global-model"}},
            }
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {"haiku": "global-model"}

            alias_manager = AliasManager()

            aliases = alias_manager.get_all_aliases()
            assert aliases["poe"]["haiku"] == "provider-model"
            assert aliases["openai"]["haiku"] == "global-model"

    def test_env_alias_override_all(self):
        """Environment variable overrides all."""
        from src.core.alias_manager import AliasManager

        with (
            patch.dict(os.environ, {"POE_ALIAS_HAIKU": "env-model"}),
            patch("src.core.provider_manager.ProviderManager") as mock_pm,
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_pm.return_value._configs = {"poe": {}}

            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {
                    "poe": {
                        "base-url": "https://test.com",
                        "aliases": {"haiku": "provider-model"},
                    }
                },
                "defaults": {"aliases": {"haiku": "global-model"}},
            }
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {"haiku": "global-model"}

            alias_manager = AliasManager()

            aliases = alias_manager.get_all_aliases()
            assert aliases["poe"]["haiku"] == "env-model"

    def test_defaults_aliases_work_for_all_providers(self):
        """defaults.aliases apply to all providers without overriding."""
        from src.core.alias_manager import AliasManager

        with (
            patch("src.core.provider_manager.ProviderManager") as mock_pm,
            patch("src.core.alias_config.AliasConfigLoader") as mock_loader,
        ):
            mock_pm.return_value._configs = {"poe": {}, "openai": {}, "anthropic": {}}

            mock_instance = mock_loader.return_value
            mock_instance.load_config.return_value = {
                "providers": {
                    "poe": {"base-url": "https://test.com"},
                    "openai": {"base-url": "https://openai.com"},
                    "anthropic": {"base-url": "https://anthropic.com"},
                },
                "defaults": {"aliases": {"common": "shared-value"}},
            }
            mock_instance.get_defaults.return_value = {}
            mock_instance.get_defaults_aliases.return_value = {"common": "shared-value"}

            alias_manager = AliasManager()

            aliases = alias_manager.get_all_aliases()
            assert aliases["poe"]["common"] == "shared-value"
            assert aliases["openai"]["common"] == "shared-value"
            assert aliases["anthropic"]["common"] == "shared-value"
