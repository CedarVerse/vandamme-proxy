"""Unit tests for ProviderConfigLoader fallback resolution."""

import pytest

from src.core.exceptions import ConfigurationError
from src.core.provider.provider_config_loader import ProviderConfigLoader


@pytest.mark.unit
class TestConfigFallback:
    """Test fallback resolution chain: env -> provider TOML -> [defaults]."""

    def setup_method(self):
        """Set up test fixtures."""
        self.loader = ProviderConfigLoader()

    def test_env_var_takes_precedence(self, monkeypatch):
        """Environment variable should take highest priority."""
        # Set env var
        monkeypatch.setenv("OPENAI_TIMEOUT", "120")

        defaults = {"timeout": "90"}

        result = self.loader._get_config_with_fallback(
            toml_config={"timeout": "60"},
            key="timeout",
            env_var="OPENAI_TIMEOUT",
            defaults_section=defaults,
            provider_name="openai",
        )

        assert result == 120

    def test_provider_toml_overrides_defaults(self, monkeypatch):
        """Provider TOML should override defaults when env var not set."""
        # Ensure env var is not set
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        result = self.loader._get_config_with_fallback(
            toml_config={"timeout": "60"},
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section={"timeout": "90"},
            provider_name="openai",
        )

        assert result == 60

    def test_defaults_used_when_missing(self, monkeypatch):
        """Defaults should be used when neither env var nor provider TOML has value."""
        # Ensure env var is not set
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        result = self.loader._get_config_with_fallback(
            toml_config={},  # No timeout in provider config
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section={"timeout": "90"},
            provider_name="openai",
        )

        assert result == 90

    def test_configuration_error_when_missing_everywhere(self, monkeypatch):
        """Should raise ConfigurationError when value is missing in all sources."""
        # Ensure env var is not set
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={},  # No timeout
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},  # No timeout
                provider_name="openai",
            )

        assert "timeout" in str(exc_info.value).lower()
        assert "openai" in str(exc_info.value)
        assert "REQUEST_TIMEOUT" in str(exc_info.value)

    def test_zero_is_valid(self, monkeypatch):
        """Zero should be a valid value (means 'disabled')."""
        monkeypatch.setenv("REQUEST_TIMEOUT", "0")

        result = self.loader._get_config_with_fallback(
            toml_config={},
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section={},
            provider_name="openai",
        )

        assert result == 0

    def test_null_string_raises_error(self, monkeypatch):
        """String 'null' should raise ConfigurationError."""
        monkeypatch.setenv("REQUEST_TIMEOUT", "null")

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={},
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},
                provider_name="openai",
            )

        assert "null" in str(exc_info.value).lower()
        assert "disable" in str(exc_info.value).lower()

    def test_negative_value_raises_error(self, monkeypatch):
        """Negative values should raise ConfigurationError."""
        monkeypatch.setenv("REQUEST_TIMEOUT", "-5")

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={},
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},
                provider_name="openai",
            )

        assert "negative" in str(exc_info.value).lower()

    def test_invalid_string_raises_error(self, monkeypatch):
        """Invalid string values should raise ConfigurationError."""
        monkeypatch.setenv("REQUEST_TIMEOUT", "not_a_number")

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={},
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},
                provider_name="openai",
            )

        assert "integer" in str(exc_info.value).lower()

    def test_integer_in_toml(self, monkeypatch):
        """Integer values in TOML should be parsed correctly."""
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        result = self.loader._get_config_with_fallback(
            toml_config={"timeout": 120},  # Integer, not string
            key="timeout",
            env_var="REQUEST_TIMEOUT",
            defaults_section={},
            provider_name="openai",
        )

        assert result == 120

    def test_negative_integer_in_toml(self, monkeypatch):
        """Negative integers in TOML should raise error."""
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={"timeout": -10},
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},
                provider_name="openai",
            )

        assert "negative" in str(exc_info.value).lower()

    def test_max_retries_fallback(self, monkeypatch):
        """Fallback should work for max-retries as well."""
        # Test with env var
        monkeypatch.setenv("MAX_RETRIES", "5")
        result = self.loader._get_config_with_fallback(
            toml_config={"max-retries": "3"},
            key="max-retries",
            env_var="MAX_RETRIES",
            defaults_section={"max-retries": "2"},
            provider_name="openai",
        )
        assert result == 5

        # Test without env var (use provider TOML)
        monkeypatch.delenv("MAX_RETRIES")
        result = self.loader._get_config_with_fallback(
            toml_config={"max-retries": "3"},
            key="max-retries",
            env_var="MAX_RETRIES",
            defaults_section={"max-retries": "2"},
            provider_name="openai",
        )
        assert result == 3

        # Test without env var or provider TOML (use defaults)
        result = self.loader._get_config_with_fallback(
            toml_config={},
            key="max-retries",
            env_var="MAX_RETRIES",
            defaults_section={"max-retries": "2"},
            provider_name="openai",
        )
        assert result == 2

    def test_error_message_includes_all_sources(self, monkeypatch):
        """Error message should list all possible configuration sources."""
        monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)

        with pytest.raises(ConfigurationError) as exc_info:
            self.loader._get_config_with_fallback(
                toml_config={},
                key="timeout",
                env_var="REQUEST_TIMEOUT",
                defaults_section={},
                provider_name="testprovider",
            )

        error_msg = str(exc_info.value)
        assert "REQUEST_TIMEOUT" in error_msg
        assert "[testprovider]" in error_msg
        assert "[defaults]" in error_msg
        assert "timeout" in error_msg
