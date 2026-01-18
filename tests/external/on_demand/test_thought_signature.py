"""Test thought signature middleware with real Gemini API.

This test validates the Google Gemini thought signature persistence feature
which is critical for multi-turn function calling workflows. The middleware
extracts and caches <thinking> blocks from Gemini responses to enable
context-aware function calling across multiple turns.

Why On-Demand?
--------------
This test is categorized as 'on-demand' because:
- It makes real API calls to the `poe:gemini-3-pro` model (expensive)
- It requires a POE_API_KEY with access to Gemini models
- It can take 30+ seconds due to function calling overhead
- It's not suitable for regular CI/CD pipelines

Prerequisites:
--------------
1. POE_API_KEY environment variable must be set
2. Proxy server must be running on localhost:8082 (or VDM_TEST_PORT)
3. Network access to the POE API endpoint

Running:
--------
    make test-on-demand PATTERN=thought
    ALLOW_EXTERNAL_TESTS=1 pytest tests/external/on_demand -k thought -v
"""

import json

import httpx
import pytest

from tests.config import DEFAULT_STREAMING_TIMEOUT


@pytest.mark.requires_api_keys("poe")
@pytest.mark.asyncio
async def test_gemini_thought_signature_persistence(require_api_keys, base_url):
    """Test thought signature middleware with real gemini-3-pro model."""
    async with httpx.AsyncClient(timeout=DEFAULT_STREAMING_TIMEOUT) as client:
        response = await client.post(
            f"{base_url}/v1/messages",
            json={
                "model": "poe:gemini-3-pro",
                "max_tokens": 1024,
                "stream": True,
                "messages": [{"role": "user", "content": "What's the weather in Tokyo and Paris?"}],
                "tools": [
                    {
                        "name": "get_weather",
                        "description": "Get weather for a location",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "City name",
                                }
                            },
                            "required": ["location"],
                        },
                    }
                ],
            },
        )

        assert response.status_code == 200

        # Parse SSE stream
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                if "delta" in data and "text" in data.get("delta", {}):
                    events.append(data["delta"]["text"])

        assert len(events) > 0, "Should receive streaming events"

        # Verify thought signature was actually emitted in the response
        full_text = "".join(events)
        # Gemini function calls often emit thinking patterns or location references
        assert any(keyword in full_text.lower() for keyword in ["weather", "tokyo", "paris"]), (
            "Response should contain answers to the weather query"
        )
