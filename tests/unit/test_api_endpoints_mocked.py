"""Unit tests for API endpoints with RESPX mocking.

Elegant HTTP-layer mocking for fast, reliable tests without external dependencies.
Converted from integration tests to use RESPX fixtures.
"""

import json

import httpx
import pytest

# Environment setup handled by conftest.py fixture
# This ensures consistent environment across all unit tests
# Import TestClient but NOT app - app will be imported in each test
# after the fixture has set up the environment
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS
from tests.fixtures.anthropic_tool_stream import anthropic_tool_use_stream_events


def _last_openai_chat_completion_request_json(mock_openai_api) -> dict:
    route = mock_openai_api.routes["POST", "https://api.openai.com/v1/chat/completions"]
    assert route.calls, "Expected at least one upstream OpenAI call"
    request = route.calls[-1].request
    return request.json()


def _last_anthropic_messages_request_json(mock_anthropic_api) -> dict:
    # respx stores routes keyed by (method, url) but url is normalized.
    route = mock_anthropic_api.routes["POST", "https://api.anthropic.com/v1/messages"]
    assert route.calls, "Expected at least one upstream Anthropic call"
    request = route.calls[-1].request
    return request.json()


def _assert_anthropic_messages_called(mock_anthropic_api) -> None:
    assert any(
        str(call.request.url) == "https://api.anthropic.com/v1/messages"
        for route in mock_anthropic_api.routes
        for call in route.calls
    ), "Expected upstream POST https://api.anthropic.com/v1/messages"


def _last_anthropic_messages_request_json_fallback(mock_anthropic_api) -> dict:
    for route in mock_anthropic_api.routes:
        for call in reversed(route.calls):
            if str(call.request.url) == "https://api.anthropic.com/v1/messages":
                content = call.request.content
                assert content is not None
                return json.loads(content.decode("utf-8"))
    raise AssertionError("Expected at least one upstream Anthropic call")


@pytest.mark.unit
def test_basic_chat_mocked(mock_openai_api, openai_chat_completion):
    """Test basic chat completion via Claude-format /v1/messages."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    # Mock OpenAI endpoint
    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=openai_chat_completion)
    )

    # Test our proxy endpoint
    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content"][0]["text"] == "Hello! How can I help you today?"
    assert data["role"] == "assistant"


@pytest.mark.unit
def test_openai_chat_completions_passthrough_mocked(mock_openai_api, openai_chat_completion):
    """Test OpenAI-compatible /v1/chat/completions passthrough (non-streaming)."""
    from src.main import app

    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=openai_chat_completion)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "openai:gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers=TEST_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
        assert data["choices"][0]["message"]["role"] == "assistant"

        # Metrics should include this request under the resolved target model.
        totals = client.get("/metrics/running-totals", headers=TEST_HEADERS)
        assert totals.status_code == 200
        assert "providers:" in totals.text
        assert "openai:" in totals.text
        assert "gpt-4" in totals.text
        assert "total_requests:" in totals.text
        assert "total_requests: 1" in totals.text


def test_openrouter_prefixed_alias_records_target_model_in_metrics(
    mock_openai_api, openai_chat_completion
):
    """Regression: requests like model='openrouter:cheap' must record the target model.

    Underlying bug: provider-prefixed aliases can leak into metrics and appear as model rows.
    This test enforces that the recorded model name is the resolved target.

    Note: OPENROUTER_ALIAS_CHEAP is set by conftest fixture to decouple this test
    from defaults.toml, allowing defaults.toml to change without breaking this test.
    """
    from src.main import app

    # OpenRouter is OpenAI-compatible, but uses a different base URL. In unit tests,
    # the provider base URL may vary; match any upstream call to /chat/completions.
    mock_openai_api.post(url__regex=r".*/chat/completions$").mock(
        return_value=httpx.Response(200, json=openai_chat_completion)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "openrouter:cheap",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers=TEST_HEADERS,
        )

        assert response.status_code == 200

        totals = client.get("/metrics/running-totals", headers=TEST_HEADERS)
        assert totals.status_code == 200
        assert "providers:" in totals.text
        assert "openrouter:" in totals.text
        assert "minimax/minimax-m2" in totals.text
        assert "openrouter:cheap" not in totals.text
        assert "total_requests: 1" in totals.text


@pytest.mark.unit
def test_openai_chat_completions_anthropic_translation_non_stream(
    mock_anthropic_api, anthropic_message_response
):
    """OpenAI /v1/chat/completions -> Anthropic provider -> OpenAI response."""
    from src.main import app

    # The OpenAI endpoint accepts the same proxy auth headers as the Claude endpoint.
    # We keep using TEST_HEADERS here for consistency.

    mock_anthropic_api.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json=anthropic_message_response)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "anthropic:claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"

    _assert_anthropic_messages_called(mock_anthropic_api)
    upstream = _last_anthropic_messages_request_json_fallback(mock_anthropic_api)
    assert upstream["model"] == "claude-3-5-sonnet-20241022"
    assert upstream["messages"][0]["role"] == "user"
    assert upstream["messages"][0]["content"][0]["type"] == "text"


@pytest.mark.unit
def test_openai_chat_completions_anthropic_translation_stream(
    mock_anthropic_api, anthropic_streaming_events
):
    """OpenAI /v1/chat/completions (stream) -> Anthropic SSE -> OpenAI SSE."""
    from src.main import app

    # Return an Anthropic SSE stream body
    stream_body = b"".join(anthropic_streaming_events)
    mock_anthropic_api.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, content=stream_body)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "anthropic:claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
                "stream": True,
            },
            headers=TEST_HEADERS,
        )

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")

        body = b"".join(response.iter_bytes())

    # Expect OpenAI-style chunks and termination
    assert b"chat.completion.chunk" in body
    assert b"data: [DONE]" in body


@pytest.mark.unit
def test_openai_chat_completions_anthropic_translation_stream_tool_calls(
    mock_anthropic_api,
):
    """Anthropic tool_use streaming -> OpenAI tool_calls streaming."""
    from src.main import app

    stream_body = b"".join(anthropic_tool_use_stream_events())
    mock_anthropic_api.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, content=stream_body)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "anthropic:claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "Compute 2+2"}],
                "max_tokens": 10,
                "stream": True,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "description": "Perform basic arithmetic",
                            "parameters": {
                                "type": "object",
                                "properties": {"expression": {"type": "string"}},
                                "required": ["expression"],
                            },
                        },
                    }
                ],
            },
            headers=TEST_HEADERS,
        )

        assert response.status_code == 200
        body = b"".join(response.iter_bytes())

    assert b"tool_calls" in body
    assert b'"name": "calculator"' in body
    assert b"data: [DONE]" in body


@pytest.mark.unit
def test_function_calling_mocked(mock_openai_api, openai_chat_completion_with_tool):
    """Test function calling with mocked OpenAI API."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    # Mock endpoint with tool response
    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=openai_chat_completion_with_tool)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": "What's 2 + 2? Use as calculator tool.",
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
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data

    # Verify tool_use in response
    tool_use_found = False
    for content_block in data.get("content", []):
        if content_block.get("type") == "tool_use":
            tool_use_found = True
            assert "id" in content_block
            assert "name" in content_block
            assert content_block["name"] == "calculator"
            assert content_block["input"] == {"expression": "2 + 2"}

    assert tool_use_found, "Expected tool_use block in response"


@pytest.mark.unit
def test_with_system_message_mocked(mock_openai_api, openai_chat_completion):
    """Test with system message using mocked API."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    # Mock endpoint
    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=openai_chat_completion)
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
                "max_tokens": 50,
                "system": (
                    "You are a helpful assistant that always ends responses with 'over and out'."
                ),
                "messages": [{"role": "user", "content": "Say hello"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert len(data["content"]) > 0


@pytest.mark.unit
def test_multimodal_mocked(mock_openai_api, openai_chat_completion):
    """Test multimodal input (text + image) with mocked API."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    # Mock endpoint
    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=openai_chat_completion)
    )

    # Small 1x1 pixel red PNG (base64)
    sample_image = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/"
        "PchI7wAAAABJRU5ErkJggg=="
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
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
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert len(data["content"]) > 0


@pytest.mark.unit
def test_conversation_with_tool_use_mocked(
    mock_openai_api, openai_chat_completion, openai_chat_completion_with_tool
):
    """Test a complete conversation with tool use and results."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    # Mock first call (tool use) and second call (final response)
    route = mock_openai_api.post("/v1/chat/completions")
    route.side_effect = [
        httpx.Response(200, json=openai_chat_completion_with_tool),
        httpx.Response(200, json=openai_chat_completion),
    ]

    with TestClient(app) as client:
        # First message with tool call
        response1 = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
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
            headers=TEST_HEADERS,
        )

        assert response1.status_code == 200
        result1 = response1.json()

        # Should have tool_use in response
        tool_use_blocks = [
            block for block in result1.get("content", []) if block.get("type") == "tool_use"
        ]
        assert len(tool_use_blocks) > 0, "Expected tool_use block in response"

        # Simulate tool execution and send result
        tool_block = tool_use_blocks[0]

        response2 = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
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
            headers=TEST_HEADERS,
        )

        assert response2.status_code == 200
        result2 = response2.json()
        assert "content" in result2


@pytest.mark.unit
def test_kimi_tool_name_sanitization_outbound_and_inbound_non_streaming(mock_openai_api):
    """Kimi requires strict tool names; we sanitize outbound and restore inbound."""
    from src.main import app

    original_tool_name = "get weather"  # contains space, should be sanitized

    # Kimi uses its own base URL; the provider config is config-driven.
    # Mock exactly what the OpenAI client will call for kimi.
    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-kimi-1",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "kimi",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "NYC"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": "What is the weather in NYC?"}],
                "tools": [
                    {
                        "name": original_tool_name,
                        "description": "Get weather",
                        "input_schema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    }
                ],
                "tool_choice": {"type": "tool", "name": original_tool_name},
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200

    import json as _json

    assert len(mock_openai_api.calls) > 0
    upstream_json = _json.loads(mock_openai_api.calls[-1].request.content)

    assert upstream_json["tools"][0]["function"]["name"] == "get_weather"
    assert upstream_json["tool_choice"]["function"]["name"] == "get_weather"

    data = response.json()
    tool_use_blocks = [b for b in data.get("content", []) if b.get("type") == "tool_use"]
    assert len(tool_use_blocks) == 1
    assert tool_use_blocks[0]["name"] == original_tool_name


@pytest.mark.unit
def test_kimi_tool_name_restoration_streaming(mock_openai_api, openai_streaming_tool_call_chunks):
    """Streaming tool_use name is restored back to the original tool name."""
    from src.main import app

    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=b"".join(openai_streaming_tool_call_chunks))
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "stream": True,
                "messages": [{"role": "user", "content": "Weather?"}],
                "tools": [
                    {
                        "name": "get weather",
                        "description": "Get weather",
                        "input_schema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    }
                ],
                "tool_choice": {"type": "auto"},
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    body = response.text
    assert '"type": "tool_use"' in body
    assert '"name": "get weather"' in body


@pytest.mark.unit
def test_token_counting_mocked():
    """Test token counting endpoint - no external API call needed."""
    # Import app after fixture setup to get fresh config
    from src.main import app

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages/count_tokens",
            json={
                "model": "openai:gpt-4",  # Use explicit provider to avoid alias conflicts
                "messages": [
                    {"role": "user", "content": "This is a test message for token counting."}
                ],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    # Token counting endpoint returns just {"input_tokens": N} without usage wrapper
    assert "input_tokens" in data
    assert data["input_tokens"] > 0


@pytest.mark.skip(
    reason="Anthropic passthrough test requires actual Anthropic provider configuration"
)
def test_anthropic_passthrough_mocked(mock_anthropic_api, anthropic_message_response):
    """Test Anthropic API passthrough format with mocked API."""
    # Skipping this test for now as it requires complex provider setup
    # The test environment uses OpenAI provider by default
    pass

    # Cleanup handled by setup_test_env fixture


@pytest.mark.unit
def test_thinking_content_block_parsed_in_request():
    """ClaudeContentBlockThinking blocks in assistant messages are accepted by the Pydantic model.

    This is a pure model validation test -- no HTTP fixtures needed.
    The thinking block is what Claude Code sends when extended thinking is enabled,
    and the proxy must be able to parse it so it can be passed through to
    Anthropic-compatible backends.
    """
    from src.models.claude import ClaudeContentBlockThinking, ClaudeMessage

    msg = ClaudeMessage(
        role="assistant",
        content=[
            ClaudeContentBlockThinking(type="thinking", thinking="Let me reason about this..."),
            {"type": "text", "text": "Here is my answer."},
        ],
    )
    assert len(msg.content) == 2
    assert msg.content[0].type == "thinking"
    assert msg.content[0].thinking == "Let me reason about this..."


@pytest.mark.unit
def test_kimi_provider_has_reasoning_content_passthrough():
    """Kimi provider config should have reasoning_content_passthrough enabled."""
    from src.core.dependencies import get_config

    cfg = get_config()
    kimi_config = cfg.provider_manager.get_provider_config("kimi")
    assert kimi_config is not None
    assert kimi_config.reasoning_content_passthrough is True


@pytest.mark.unit
def test_opencodego_provider_has_reasoning_content_passthrough():
    """OpenCodeGo provider config should have reasoning_content_passthrough enabled."""
    from src.core.dependencies import get_config

    cfg = get_config()
    opencodego_config = cfg.provider_manager.get_provider_config("opencodego")
    assert opencodego_config is not None
    assert opencodego_config.reasoning_content_passthrough is True


@pytest.mark.unit
def test_openai_provider_no_reasoning_content_passthrough():
    """Providers without the flag should default to False."""
    from src.core.dependencies import get_config

    cfg = get_config()
    openai_config = cfg.provider_manager.get_provider_config("openai")
    assert openai_config is not None
    assert openai_config.reasoning_content_passthrough is False


@pytest.mark.unit
def test_kimi_reasoning_content_request_passthrough(mock_openai_api):
    """Thinking blocks in assistant messages are forwarded as reasoning_content to Kimi.

    When a provider has reasoning_content_passthrough=True (e.g. Kimi), the proxy
    must extract thinking blocks from Claude-format assistant messages and place them
    into the OpenAI-format 'reasoning_content' field so the upstream provider can
    consume chain-of-thought context.
    """
    from src.main import app

    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-kimi-r1",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "kimi-k2-thinking-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Done"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "Let me think..."},
                            {"type": "text", "text": "Hi there!"},
                        ],
                    },
                    {"role": "user", "content": "Thanks"},
                ],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200

    # Verify the upstream request preserved reasoning_content
    upstream_json = json.loads(mock_openai_api.calls[-1].request.content)
    assistant_msg = [m for m in upstream_json["messages"] if m["role"] == "assistant"][0]
    assert "reasoning_content" in assistant_msg
    assert assistant_msg["reasoning_content"] == "Let me think..."


@pytest.mark.unit
def test_non_thinking_provider_no_reasoning_content(mock_openai_api):
    """Non-thinking providers should NOT get reasoning_content in forwarded requests.

    Providers without reasoning_content_passthrough (e.g. OpenAI) must silently
    drop thinking blocks from assistant messages rather than forwarding them,
    because those providers don't understand the reasoning_content field.
    """
    from src.main import app

    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Done"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",
                "max_tokens": 200,
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "Let me think..."},
                            {"type": "text", "text": "Hi there!"},
                        ],
                    },
                    {"role": "user", "content": "Thanks"},
                ],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    upstream_json = json.loads(mock_openai_api.calls[-1].request.content)
    assistant_msg = [m for m in upstream_json["messages"] if m["role"] == "assistant"][0]
    assert "reasoning_content" not in assistant_msg


@pytest.mark.unit
def test_kimi_reasoning_content_response_non_streaming(mock_openai_api):
    """reasoning_content from upstream is converted to a thinking content block.

    When a provider has reasoning_content_passthrough=True (e.g. Kimi), the proxy
    must convert the upstream 'reasoning_content' field into a Claude-format
    'thinking' content block so the Claude client can display chain-of-thought.
    """
    from src.main import app

    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-kimi-r2",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "kimi-k2-thinking-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                            "reasoning_content": "I need to think about this carefully. First...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": "What is the answer?"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    thinking_blocks = [b for b in data["content"] if b.get("type") == "thinking"]
    assert len(thinking_blocks) == 1
    assert thinking_blocks[0]["thinking"] == "I need to think about this carefully. First..."
    # Text block should also be present
    text_blocks = [b for b in data["content"] if b.get("type") == "text"]
    assert len(text_blocks) == 1
    assert text_blocks[0]["text"] == "The answer is 42."


@pytest.mark.unit
def test_non_thinking_provider_ignores_reasoning_content_response(mock_openai_api):
    """Providers without reasoning_content_passthrough must NOT produce thinking blocks.

    Even if an upstream provider unexpectedly returns reasoning_content, the proxy
    must ignore it for providers that don't have the flag enabled. This prevents
    thinking blocks from leaking into responses to clients that don't expect them.
    """
    from src.main import app

    # OpenAI does NOT have reasoning_content_passthrough enabled
    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-openai-r3",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                            # Unexpected reasoning_content from a provider that shouldn't emit it
                            "reasoning_content": "I need to think about this carefully...",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": "What is the answer?"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    # No thinking blocks should be present for non-flagged providers
    thinking_blocks = [b for b in data["content"] if b.get("type") == "thinking"]
    assert len(thinking_blocks) == 0
    # Only text block should be present
    text_blocks = [b for b in data["content"] if b.get("type") == "text"]
    assert len(text_blocks) == 1
    assert text_blocks[0]["text"] == "The answer is 42."


@pytest.mark.unit
def test_kimi_reasoning_content_response_streaming(mock_openai_api):
    """Streaming reasoning_content deltas are converted to thinking SSE events.

    When a provider has reasoning_content_passthrough=True (e.g. Kimi), the proxy
    must convert upstream reasoning_content deltas into Claude-format thinking
    content_block_start/delta/stop SSE events during streaming.

    This exercises the state machine's ability to:
    1. Close the premature text block (opened by initial_events)
    2. Open a thinking block at index 0
    3. Re-open text block at index 1
    4. Emit thinking_delta events for each reasoning_content chunk
    5. Close both blocks in final_events
    """
    from src.main import app

    def _chunk(delta: dict, finish_reason=None) -> bytes:
        """Build a single OpenAI SSE chunk as raw bytes."""
        payload = {
            "id": "chatcmpl-rs1",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "kimi",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    chunks = [
        _chunk({"role": "assistant"}),
        _chunk({"reasoning_content": "Let me"}),
        _chunk({"reasoning_content": " think..."}),
        _chunk({"content": "The answer."}),
        _chunk({}, finish_reason="stop"),
        b"data: [DONE]\n\n",
    ]

    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=b"".join(chunks))
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "stream": True,
                "messages": [{"role": "user", "content": "Think and answer"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    body = response.text
    # Should contain thinking content block start and delta events
    assert '"type": "thinking"' in body, "Expected thinking content block start in SSE stream"
    assert "thinking_delta" in body, "Expected thinking_delta event in SSE stream"
    assert '"thinking": "Let me"' in body, "Expected first reasoning chunk as thinking delta"
    assert '"thinking": " think..."' in body, "Expected second reasoning chunk as thinking delta"
    # Should also contain the text content
    assert "The answer." in body, "Expected text content in SSE stream"


@pytest.mark.unit
def test_kimi_reasoning_with_tool_calls_multiturn(mock_openai_api):
    """Multi-turn: assistant message with both thinking and tool_use preserves reasoning_content.

    This reproduces the original error that motivated the reasoning-content passthrough
    feature: Kimi's API returns 400 when ``reasoning_content`` is missing from assistant
    tool-call messages in multi-turn conversations.  The proxy must forward thinking
    blocks as ``reasoning_content`` *alongside* ``tool_calls`` in the upstream request,
    and conversely convert ``reasoning_content`` + ``tool_calls`` in the upstream
    response back into Claude-format thinking + tool_use content blocks.

    Both directions are validated:
    - Request path: Claude thinking blocks -> OpenAI ``reasoning_content`` field
    - Response path: OpenAI ``reasoning_content`` -> Claude thinking content block
    - Tool calls are preserved in both directions with name sanitization.
    """
    from src.main import app

    mock_openai_api.post("https://api.kimi.com/coding/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-kimi-mt",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "kimi-k2-thinking-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": "I should call a tool.",
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "NYC"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "kimi:sonnet",
                "max_tokens": 200,
                "messages": [
                    {"role": "user", "content": "Check weather in NYC"},
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "I should call a tool."},
                            {
                                "type": "tool_use",
                                "id": "toolu_prev",
                                "name": "get weather",
                                "input": {"city": "NYC"},
                            },
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "toolu_prev",
                                "content": "Sunny, 72F",
                            }
                        ],
                    },
                ],
                "tools": [
                    {
                        "name": "get weather",
                        "description": "Get weather",
                        "input_schema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    }
                ],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200

    # Verify upstream request preserved reasoning_content on the assistant tool-call message.
    # This is the critical assertion: without reasoning_content, Kimi returns 400.
    upstream_json = json.loads(mock_openai_api.calls[-1].request.content)
    assistant_msgs = [m for m in upstream_json["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert "reasoning_content" in assistant_msgs[0]
    assert assistant_msgs[0]["reasoning_content"] == "I should call a tool."
    assert "tool_calls" in assistant_msgs[0]
    assert assistant_msgs[0]["tool_calls"][0]["function"]["name"] == "get_weather"

    # Verify response includes thinking block from upstream reasoning_content
    data = response.json()
    thinking_blocks = [b for b in data["content"] if b.get("type") == "thinking"]
    assert len(thinking_blocks) == 1
    assert thinking_blocks[0]["thinking"] == "I should call a tool."
    # Verify tool_use block is present with original (un-sanitized) name
    tool_use_blocks = [b for b in data["content"] if b.get("type") == "tool_use"]
    assert len(tool_use_blocks) == 1
    assert tool_use_blocks[0]["name"] == "get weather"


@pytest.mark.unit
def test_non_thinking_provider_ignores_reasoning_content_streaming(mock_openai_api):
    """Providers without reasoning_content_passthrough must NOT produce thinking SSE events.

    Even if an upstream provider unexpectedly returns reasoning_content deltas in a
    streaming response, the proxy must ignore them for providers that don't have the
    flag enabled. This prevents thinking blocks from leaking into SSE streams for
    clients that don't expect them.
    """
    from src.main import app

    def _chunk(delta: dict, finish_reason=None) -> bytes:
        """Build a single OpenAI SSE chunk as raw bytes."""
        payload = {
            "id": "chatcmpl-nr1",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload)}\n\n".encode()

    chunks = [
        _chunk({"role": "assistant"}),
        _chunk({"reasoning_content": "Unexpected reasoning"}),
        _chunk({"content": "Just text."}),
        _chunk({}, finish_reason="stop"),
        b"data: [DONE]\n\n",
    ]

    mock_openai_api.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=b"".join(chunks))
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "openai:gpt-4",
                "max_tokens": 200,
                "stream": True,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=TEST_HEADERS,
        )

    assert response.status_code == 200
    body = response.text
    # NO thinking events should be present for non-flagged providers
    assert '"type": "thinking"' not in body, (
        "Thinking block must NOT appear for non-flagged provider"
    )
    assert "thinking_delta" not in body, "Thinking delta must NOT appear for non-flagged provider"
    # Text content should still be present
    assert "Just text." in body
