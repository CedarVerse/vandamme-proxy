"""Tests for AliasService."""

from unittest.mock import MagicMock

import pytest

from src.core.alias_service import AliasService


@pytest.mark.unit
def test_get_active_aliases_with_providers(mock_alias_manager, mock_provider_manager):
    """Test get_active_aliases returns filtered aliases."""
    mock_alias_manager.get_all_aliases.return_value = {
        "openai": {"haiku": "gpt-4o-mini"},
        "poe": {"sonnet": "glm-4.6"},
        "anthropic": {"opus": "claude-3-opus-20240229"},
    }
    mock_provider_manager.list_providers.return_value = {
        "openai": MagicMock(),
        "poe": MagicMock(),
    }

    service = AliasService(mock_alias_manager, mock_provider_manager)
    result = service.get_active_aliases()

    assert result == {
        "openai": {"haiku": "gpt-4o-mini"},
        "poe": {"sonnet": "glm-4.6"},
    }
    # anthropic excluded - not in active providers
    assert "anthropic" not in result


@pytest.mark.unit
def test_get_active_aliases_empty_providers(mock_alias_manager, mock_provider_manager):
    """Test get_active_aliases returns empty dict when no providers active."""
    mock_alias_manager.get_all_aliases.return_value = {
        "openai": {"haiku": "gpt-4o-mini"},
    }
    mock_provider_manager.list_providers.return_value = {}

    service = AliasService(mock_alias_manager, mock_provider_manager)
    result = service.get_active_aliases()

    assert result == {}


@pytest.mark.unit
def test_get_active_aliases_provider_manager_error(mock_alias_manager, mock_provider_manager):
    """Test get_active_aliases returns empty dict on ProviderManager error."""
    mock_provider_manager.list_providers.side_effect = RuntimeError("Not initialized")

    service = AliasService(mock_alias_manager, mock_provider_manager)
    result = service.get_active_aliases()

    assert result == {}


@pytest.mark.unit
def test_get_active_aliases_provider_manager_attribute_error(
    mock_alias_manager, mock_provider_manager
):
    """Test get_active_aliases returns empty dict when ProviderManager not initialized."""
    mock_provider_manager.list_providers.side_effect = AttributeError("Not initialized")

    service = AliasService(mock_alias_manager, mock_provider_manager)
    result = service.get_active_aliases()

    assert result == {}


@pytest.mark.unit
def test_get_active_aliases_all_providers_active(mock_alias_manager, mock_provider_manager):
    """Test get_active_aliases returns all aliases when all providers are active."""
    mock_alias_manager.get_all_aliases.return_value = {
        "openai": {"haiku": "gpt-4o-mini"},
        "poe": {"sonnet": "glm-4.6"},
    }
    mock_provider_manager.list_providers.return_value = {
        "openai": MagicMock(),
        "poe": MagicMock(),
    }

    service = AliasService(mock_alias_manager, mock_provider_manager)
    result = service.get_active_aliases()

    assert result == {
        "openai": {"haiku": "gpt-4o-mini"},
        "poe": {"sonnet": "glm-4.6"},
    }


@pytest.mark.unit
def test_print_alias_summary_no_aliases(mock_alias_manager, mock_provider_manager, capsys):
    """Test print_alias_summary does nothing when no aliases configured."""
    mock_alias_manager.get_all_aliases.return_value = {}
    mock_alias_manager._fallback_aliases = {}

    service = AliasService(mock_alias_manager, mock_provider_manager)
    service.print_alias_summary()

    captured = capsys.readouterr()
    # Should not print anything when no aliases
    assert "Model Aliases" not in captured.out


@pytest.mark.unit
def test_print_alias_summary_with_aliases(mock_alias_manager, mock_provider_manager, capsys):
    """Test print_alias_summary prints formatted aliases."""
    mock_alias_manager.get_all_aliases.return_value = {
        "openai": {"haiku": "gpt-4o-mini", "fast": "gpt-4o"},
    }
    mock_alias_manager._fallback_aliases = {}
    mock_provider_manager.list_providers.return_value = {
        "openai": MagicMock(),
    }

    service = AliasService(mock_alias_manager, mock_provider_manager)
    service.print_alias_summary()

    captured = capsys.readouterr()
    assert "Model Aliases" in captured.out
    assert "openai" in captured.out
    assert "haiku" in captured.out
    assert "gpt-4o-mini" in captured.out


@pytest.fixture
def mock_alias_manager():
    """Mock AliasManager."""
    return MagicMock()


@pytest.fixture
def mock_provider_manager():
    """Mock ProviderManager."""
    return MagicMock()
