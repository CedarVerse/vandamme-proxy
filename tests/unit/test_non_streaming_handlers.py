"""Unit tests for non-streaming handler strategy pattern.

Covers:
- AnthropicNonStreamingHandler (happy path, error detection, metrics)
- OpenAINonStreamingHandler (happy path, error detection, tool calls, metrics)
- get_non_streaming_handler factory
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.services.non_streaming_handlers import (
    AnthropicNonStreamingHandler,
    OpenAINonStreamingHandler,
    get_non_streaming_handler,
)
from src.core.provider_config import ProviderConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anthropic_response():
    """Standard Anthropic message response with usage."""
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Hello!"}],
        "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_tokens": 2},
    }


@pytest.fixture
def mock_openai_response():
    """Standard OpenAI chat completion response with usage."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_context(
    *,
    is_metrics_enabled=True,
    metrics=None,
    tracker=None,
    request_id="req-ns",
    provider_name="test-provider",
    provider_config=None,
    log_request_metrics=True,
    middleware_chain=None,
):
    """Build a MagicMock that mimics ApiRequestContext for handler tests.

    Using MagicMock instead of the real RequestContext because the real
    one is a frozen dataclass requiring a ClaudeMessagesRequest instance.
    """
    if tracker is None and is_metrics_enabled:
        tracker = MagicMock()
        tracker.end_request = AsyncMock()

    ctx = MagicMock()
    ctx.is_metrics_enabled = is_metrics_enabled
    ctx.request_id = request_id
    ctx.provider_name = provider_name
    ctx.provider_config = provider_config or ProviderConfig(
        name=provider_name,
        api_key="test-key",
        base_url="https://api.test.com",
    )
    ctx.tracker = tracker
    ctx.metrics = metrics if metrics is not None else (MagicMock() if is_metrics_enabled else None)
    ctx.config = MagicMock()
    ctx.config.log_request_metrics = log_request_metrics
    ctx.config.provider_manager = MagicMock()
    ctx.config.provider_manager.middleware_chain = middleware_chain
    ctx.openai_client = AsyncMock()
    ctx.start_time = 1000.0
    ctx.request_size = 42
    ctx.tool_use_count = 0
    ctx.tool_result_count = 0
    ctx.tool_name_map_inverse = None
    ctx.client_api_key = None
    ctx.provider_api_key = None
    ctx.request = MagicMock()  # ClaudeMessagesRequest mock
    ctx.openai_request = MagicMock()
    ctx.http_request = MagicMock()
    return ctx


# ===========================================================================
# AnthropicNonStreamingHandler
# ===========================================================================


class TestAnthropicNonStreamingHandler:
    """Tests for the Anthropic-format non-streaming handler."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_happy_path_returns_200(self, mock_anthropic_response):
        """Successful response -> 200, tracker.end_request called."""
        ctx = _make_context(provider_name="anthropic")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_anthropic_response)

        handler = AnthropicNonStreamingHandler()
        with (
            patch(
                "src.api.services.non_streaming_handlers.build_anthropic_passthrough_request",
                return_value=("claude-3-5-sonnet", {}),
            ),
            patch(
                "src.core.model_manager_runtime.get_model_manager",
            ),
        ):
            response = await handler.handle_with_context(ctx)

        assert response.status_code == 200
        assert response.body is not None
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_detection_raises_http_exception(self):
        """Anthropic error response -> HTTPException(500), tracker still called."""
        error_resp = {"type": "error", "error": {"type": "overloaded", "message": "busy"}}
        ctx = _make_context(provider_name="anthropic")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=error_resp)

        handler = AnthropicNonStreamingHandler()
        with (
            patch(
                "src.api.services.non_streaming_handlers.build_anthropic_passthrough_request",
                return_value=("claude-3-5-sonnet", {}),
            ),
            patch(
                "src.core.model_manager_runtime.get_model_manager",
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await handler.handle_with_context(ctx)

        assert exc_info.value.status_code == 500
        assert "busy" in exc_info.value.detail
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_response_raises_http_exception(self):
        """None response -> HTTPException(500), tracker still called."""
        ctx = _make_context(provider_name="anthropic")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=None)

        handler = AnthropicNonStreamingHandler()
        with (
            patch(
                "src.api.services.non_streaming_handlers.build_anthropic_passthrough_request",
                return_value=("claude-3-5-sonnet", {}),
            ),
            patch(
                "src.core.model_manager_runtime.get_model_manager",
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await handler.handle_with_context(ctx)

        assert exc_info.value.status_code == 500
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_disabled_no_crash(self, mock_anthropic_response):
        """Metrics disabled -> returns 200, no crash from missing tracker."""
        ctx = _make_context(
            is_metrics_enabled=False,
            metrics=None,
            tracker=None,
            provider_name="anthropic",
        )
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_anthropic_response)

        handler = AnthropicNonStreamingHandler()
        with (
            patch(
                "src.api.services.non_streaming_handlers.build_anthropic_passthrough_request",
                return_value=("claude-3-5-sonnet", {}),
            ),
            patch(
                "src.core.model_manager_runtime.get_model_manager",
            ),
        ):
            response = await handler.handle_with_context(ctx)

        assert response.status_code == 200

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_token_extraction_anthropic(self, mock_anthropic_response):
        """Verify token metrics are populated from Anthropic usage fields."""
        ctx = _make_context(provider_name="anthropic")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_anthropic_response)

        handler = AnthropicNonStreamingHandler()
        with (
            patch(
                "src.api.services.non_streaming_handlers.build_anthropic_passthrough_request",
                return_value=("claude-3-5-sonnet", {}),
            ),
            patch(
                "src.core.model_manager_runtime.get_model_manager",
            ),
        ):
            await handler.handle_with_context(ctx)

        assert ctx.metrics.input_tokens == 10
        assert ctx.metrics.output_tokens == 5
        assert ctx.metrics.cache_read_tokens == 2


# ===========================================================================
# OpenAINonStreamingHandler
# ===========================================================================


class TestOpenAINonStreamingHandler:
    """Tests for the OpenAI-format non-streaming handler."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_happy_path_returns_200(self, mock_openai_response):
        """Successful response -> 200, tracker.end_request called."""
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_openai_response)

        handler = OpenAINonStreamingHandler()
        with patch(
            "src.api.services.non_streaming_handlers.convert_openai_to_claude_response",
            return_value={"id": "conv-123", "type": "message", "content": "Hi"},
        ):
            response = await handler.handle_with_context(ctx)

        assert response.status_code == 200
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_with_msg_key(self):
        """OpenAI-style {'msg': ..., 'code': 401} -> HTTPException(401)."""
        error_resp = {"msg": "invalid key", "code": 401}
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=error_resp)

        handler = OpenAINonStreamingHandler()
        with pytest.raises(HTTPException) as exc_info:
            await handler.handle_with_context(ctx)

        assert exc_info.value.status_code == 401
        assert "invalid key" in exc_info.value.detail
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_with_error_key(self):
        """OpenAI-style {'error': {'message': ...}} -> HTTPException(500)."""
        error_resp = {"error": {"message": "rate limited"}}
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=error_resp)

        handler = OpenAINonStreamingHandler()
        with pytest.raises(HTTPException) as exc_info:
            await handler.handle_with_context(ctx)

        assert exc_info.value.status_code == 500
        assert "rate limited" in exc_info.value.detail
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_response_raises_http_exception(self):
        """None response -> HTTPException(500), tracker still called."""
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=None)

        handler = OpenAINonStreamingHandler()
        with pytest.raises(HTTPException) as exc_info:
            await handler.handle_with_context(ctx)

        assert exc_info.value.status_code == 500
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tool_call_counting(self):
        """Response with tool_calls -> metrics.tool_call_count = 2."""
        response_with_tools = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Let me check.",
                        "tool_calls": [
                            {"id": "c1", "type": "function", "function": {"name": "get_weather"}},
                            {"id": "c2", "type": "function", "function": {"name": "get_time"}},
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20},
        }
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=response_with_tools)

        handler = OpenAINonStreamingHandler()
        with patch(
            "src.api.services.non_streaming_handlers.convert_openai_to_claude_response",
            return_value={"id": "conv-tool", "type": "message", "content": "results"},
        ):
            await handler.handle_with_context(ctx)

        assert ctx.metrics.tool_call_count == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_token_extraction_openai(self, mock_openai_response):
        """Verify token metrics from OpenAI usage fields."""
        ctx = _make_context(provider_name="openai")
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_openai_response)

        handler = OpenAINonStreamingHandler()
        with patch(
            "src.api.services.non_streaming_handlers.convert_openai_to_claude_response",
            return_value={"id": "conv-tok", "type": "message", "content": "Hi"},
        ):
            await handler.handle_with_context(ctx)

        assert ctx.metrics.input_tokens == 10
        assert ctx.metrics.output_tokens == 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bug_fix_tracker_called_when_log_request_metrics_false(
        self,
        mock_openai_response,
    ):
        """BUG FIX: tracker.end_request called even when log_request_metrics=False.

        The old OpenAI handler gated tracker.end_request() behind the
        log_request_metrics verbose-logging flag.  The centralized
        finalize_nonstreaming_metrics fixes this by always calling
        tracker.end_request() within the is_metrics_enabled guard.
        """
        ctx = _make_context(
            provider_name="openai",
            log_request_metrics=False,
        )
        ctx.openai_client.create_chat_completion = AsyncMock(return_value=mock_openai_response)

        handler = OpenAINonStreamingHandler()
        with patch(
            "src.api.services.non_streaming_handlers.convert_openai_to_claude_response",
            return_value={"id": "conv-fix", "type": "message", "content": "fixed"},
        ):
            response = await handler.handle_with_context(ctx)

        assert response.status_code == 200
        # The critical assertion: tracker MUST be called regardless of
        # log_request_metrics.
        ctx.tracker.end_request.assert_awaited_once_with("req-ns")


# ===========================================================================
# Factory: get_non_streaming_handler
# ===========================================================================


class TestGetNonStreamingHandler:
    """Tests for the handler factory function."""

    @pytest.mark.unit
    def test_openai_format(self):
        config = MagicMock()
        pc = ProviderConfig(name="openai", api_key="k", base_url="https://api.openai.com")
        handler = get_non_streaming_handler(config, pc)
        assert isinstance(handler, OpenAINonStreamingHandler)

    @pytest.mark.unit
    def test_anthropic_format(self):
        config = MagicMock()
        pc = ProviderConfig(
            name="anthropic",
            api_key="k",
            base_url="https://api.anthropic.com",
            api_format="anthropic",
        )
        handler = get_non_streaming_handler(config, pc)
        assert isinstance(handler, AnthropicNonStreamingHandler)

    @pytest.mark.unit
    def test_responses_format_raises_value_error(self):
        """Responses format requires streaming; non-streaming is not supported."""
        config = MagicMock()
        pc = ProviderConfig(
            name="chatgpt",
            api_key="k",
            base_url="https://api.openai.com",
            api_format="responses",
        )
        with pytest.raises(ValueError, match="requires streaming"):
            get_non_streaming_handler(config, pc)
