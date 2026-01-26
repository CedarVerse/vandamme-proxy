"""Debug test to check provider loading."""

import os

import pytest


@pytest.mark.unit
def test_check_provider_loading():
    """Check provider loading."""
    from src.core.config import Config

    config = Config()

    print(f"OPENAI_API_KEY env: {repr(os.environ.get('OPENAI_API_KEY'))}")
    print(f"_loaded: {config.provider_manager._loaded}")
    print(f"registry keys: {list(config.provider_manager._registry.list_all().keys())}")

    # Try to reload
    config.provider_manager.load_provider_configs()
    print(
        f"After reload - registry keys: {list(config.provider_manager._registry.list_all().keys())}"
    )
