"""Integration test for models_url in health endpoint."""

import os

import httpx
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get test port from environment or use default
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_includes_models_url():
    """Health endpoint includes models_url for configured providers."""
    import yaml

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

        assert response.status_code == 200

        # Parse YAML response
        health_data = yaml.safe_load(response.text)

        # Verify providers section exists
        assert "providers" in health_data
        providers = health_data["providers"]

        # Check that models_url key exists in provider info (may be null if not configured)
        # At minimum, the key should be present
        for _provider_name, provider_info in providers.items():
            if isinstance(provider_info, dict):
                # models_url should be present in provider info
                assert "models_url" in provider_info
                # Value can be None, string, or missing - just verify key exists
                models_url = provider_info.get("models_url")
                assert models_url is None or isinstance(models_url, str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_models_url_structure():
    """Health endpoint models_url field has correct structure."""
    import yaml

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

        assert response.status_code == 200

        health_data = yaml.safe_load(response.text)
        providers = health_data.get("providers", {})

        # Verify structure is consistent
        for _provider_name, provider_info in providers.items():
            if isinstance(provider_info, dict):
                # Check expected keys exist
                assert "api_format" in provider_info
                assert "base_url" in provider_info
                assert "auth_mode" in provider_info
                assert "models_url" in provider_info

                # models_url should be string or None
                models_url = provider_info.get("models_url")
                assert models_url is None or isinstance(models_url, str)
