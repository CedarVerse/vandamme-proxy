"""External tests for ZAI provider.

These tests make real API calls to ZAI and require:
1. A running proxy server
2. ZAI_API_KEY environment variable
3. ALLOW_EXTERNAL_TESTS=1 environment variable
"""

import os

import httpx
import pytest

# Get test configuration
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.external
@pytest.mark.requires_api_keys("zai")
@pytest.mark.asyncio
async def test_zai_anthropic_passthrough():
    """Test Anthropic API passthrough format with real ZAI API."""
    if not os.getenv("ZAI_API_KEY"):
        pytest.skip("ZAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zai:GLM-4.7",
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "role" in data
        assert data["role"] == "assistant"
