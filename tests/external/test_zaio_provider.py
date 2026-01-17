"""External tests for ZAIO provider.

These tests make real API calls to ZAIO and require:
1. A running proxy server
2. ZAIO_API_KEY environment variable
3. ALLOW_EXTERNAL_TESTS=1 environment variable
"""

import os

import httpx
import pytest

# Get test configuration
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_basic_chat():
    """Test basic chat completion with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "Say 'Hello world'"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0
        assert "role" in data
        assert data["role"] == "assistant"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_streaming_chat():
    """Test streaming chat completion with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with (
        httpx.AsyncClient(timeout=30.0) as client,
        client.stream(
            "POST",
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.5-Air",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
            },
        ) as response,
    ):
        assert response.status_code == 200

        # Collect streamed events
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(line[6:])  # Remove "data: " prefix

        # Should have at least some events
        assert len(events) > 0

        # Check for event stream format
        assert any("message_start" in event for event in events)
        assert any("content_block_start" in event for event in events)
        assert any("content_block_stop" in event for event in events)
        assert any("message_stop" in event for event in events)


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_function_calling():
    """Test function calling with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": "What's 2 + 2? Use the calculator tool.",
                    }
                ],
                "tools": [
                    {
                        "name": "calculator",
                        "description": "Perform basic arithmetic",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression",
                                },
                            },
                            "required": ["expression"],
                        },
                    }
                ],
                "tool_choice": {"type": "auto"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data

        # Should have tool_use in content
        tool_use_found = False
        for content_block in data.get("content", []):
            if content_block.get("type") == "tool_use":
                tool_use_found = True
                assert "id" in content_block
                assert "name" in content_block
                assert content_block["name"] == "calculator"

        assert tool_use_found, "Expected tool_use block in response"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_with_system_message():
    """Test with system message."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "system": (
                    "You are a helpful assistant that always ends responses with 'over and out'."
                ),
                "messages": [{"role": "user", "content": "Say hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0

        # Check that the response follows the system instruction
        content_text = data["content"][0].get("text", "").lower()
        assert "over and out" in content_text


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_multimodal():
    """Test multimodal input (text + image)."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Small 1x1 pixel red PNG
        sample_image = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/"
            "PchI7wAAAABJRU5ErkJggg=="
        )

        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What color is this image?"},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": sample_image,
                                },
                            },
                        ],
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_conversation_with_tool_use():
    """Test a complete conversation with tool use and results."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # First message with tool call
        response1 = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": "Calculate 25 * 4"}],
                "tools": [
                    {
                        "name": "calculator",
                        "description": "Perform arithmetic calculations",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to calculate",
                                }
                            },
                            "required": ["expression"],
                        },
                    }
                ],
            },
        )

        assert response1.status_code == 200
        result1 = response1.json()

        # Note: tool calling behavior is provider/model dependent
        tool_use_blocks = [
            block for block in result1.get("content", []) if block.get("type") == "tool_use"
        ]
        if not tool_use_blocks:
            content_text = " ".join(
                block.get("text", "")
                for block in result1.get("content", [])
                if block.get("type") == "text"
            ).lower()
            assert "100" in content_text
            return

        # Simulate tool execution and send result
        tool_block = tool_use_blocks[0]

        response2 = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "messages": [
                    {"role": "user", "content": "Calculate 25 * 4"},
                    {"role": "assistant", "content": result1["content"]},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_block["id"],
                                "content": "100",
                            }
                        ],
                    },
                ],
            },
        )

        assert response2.status_code == 200
        result2 = response2.json()
        assert "content" in result2

        # Should acknowledge the calculation result
        content_text = " ".join(
            block.get("text", "")
            for block in result2.get("content", [])
            if block.get("type") == "text"
        ).lower()
        assert "100" in content_text


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_token_counting():
    """Test token counting endpoint."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages/count_tokens",
            json={
                "model": "zaio:GLM-4.7",
                "messages": [
                    {"role": "user", "content": "This is a test message for token counting."}
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "input_tokens" in data
        assert data["input_tokens"] > 0
