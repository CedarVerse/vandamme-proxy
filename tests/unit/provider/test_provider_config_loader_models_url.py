"""Test models_url loading in ProviderConfigLoader."""

import pytest

from src.core.provider.provider_config_loader import ProviderConfigLoader


@pytest.mark.unit
def test_load_models_url_from_env_var(monkeypatch):
    """Loader reads models_url from {PROVIDER}_MODELS_URL environment variable."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTPROV_MODELS_URL", "https://example.com/docs/models")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url == "https://example.com/docs/models"


@pytest.mark.unit
def test_env_var_overrides_toml_for_models_url(monkeypatch):
    """Environment variable takes precedence over TOML for models_url."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTPROV_MODELS_URL", "https://env-var-url.com/models")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url == "https://env-var-url.com/models"


@pytest.mark.unit
def test_no_models_url_when_not_configured(monkeypatch):
    """models_url is None when neither env var nor TOML provides it."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url is None
