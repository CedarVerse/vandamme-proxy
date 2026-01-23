"""Test models_url field in ProviderConfig."""

import pytest

from src.core.provider_config import ProviderConfig


@pytest.mark.unit
def test_provider_config_with_models_url():
    """ProviderConfig accepts models_url field."""
    config = ProviderConfig(
        name="test-provider",
        api_key="test-key",
        base_url="https://api.example.com/v1",
        models_url="https://example.com/docs/models",
    )
    assert config.models_url == "https://example.com/docs/models"


@pytest.mark.unit
def test_provider_config_default_models_url():
    """ProviderConfig models_url defaults to None."""
    config = ProviderConfig(
        name="test-provider",
        api_key="test-key",
        base_url="https://api.example.com/v1",
    )
    assert config.models_url is None
