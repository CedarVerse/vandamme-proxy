"""Unit tests for shared error handling utilities.

Covers:
- ErrorInfo dataclass construction and immutability
- detect_error_response heuristic for all known provider error shapes
- extract_error_info priority-ordered extraction from error responses
- TokenFieldMap presets (OPENAI / ANTHROPIC)
- finalize_nonstreaming_metrics (token extraction, tool call counting, bug fix)
- finalize_metrics_on_streaming_error
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.services.error_handling import (
    ANTHROPIC_TOKEN_FIELDS,
    OPENAI_TOKEN_FIELDS,
    ErrorInfo,
    detect_error_response,
    extract_error_info,
    finalize_metrics_on_streaming_error,
    finalize_nonstreaming_metrics,
)
from src.core.error_types import ErrorType

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_context(
    *,
    is_metrics_enabled=True,
    metrics=None,
    tracker=None,
    request_id="req-test",
    config_log_request_metrics=True,
):
    """Build a MagicMock that mimics ApiRequestContext for metrics tests.

    The real RequestContext is a frozen dataclass that requires a
    ClaudeMessagesRequest, so we use MagicMock to isolate the metrics
    logic without coupling to the full request model.
    """
    ctx = MagicMock()
    ctx.is_metrics_enabled = is_metrics_enabled
    ctx.request_id = request_id
    ctx.tracker = tracker
    ctx.metrics = metrics if metrics is not None else (MagicMock() if is_metrics_enabled else None)
    ctx.config = MagicMock()
    ctx.config.log_request_metrics = config_log_request_metrics
    return ctx


# ===========================================================================
# ErrorInfo
# ===========================================================================


class TestErrorInfo:
    """Tests for the ErrorInfo frozen dataclass."""

    @pytest.mark.unit
    def test_construction_message_only(self):
        """Code defaults to None when omitted."""
        info = ErrorInfo(message="something went wrong")
        assert info.message == "something went wrong"
        assert info.code is None

    @pytest.mark.unit
    def test_construction_with_int_code(self):
        info = ErrorInfo(message="unauthorized", code=401)
        assert info.code == 401

    @pytest.mark.unit
    def test_construction_with_string_code(self):
        info = ErrorInfo(message="rate limited", code="rate_limit")
        assert info.code == "rate_limit"

    @pytest.mark.unit
    def test_frozen_raises_on_mutation(self):
        """frozen=True prevents attribute assignment."""
        info = ErrorInfo(message="immutable")
        with pytest.raises(AttributeError):
            info.message = "mutated"


# ===========================================================================
# detect_error_response
# ===========================================================================


class TestDetectErrorResponse:
    """Tests for the detect_error_response heuristic."""

    @pytest.mark.unit
    def test_none_returns_true(self):
        assert detect_error_response(None) is True

    @pytest.mark.unit
    def test_anthropic_error_dict_returns_true(self):
        resp = {"type": "error", "error": {"type": "overloaded", "message": "busy"}}
        assert detect_error_response(resp) is True

    @pytest.mark.unit
    def test_valid_message_type_returns_false(self):
        resp = {"type": "message", "content": [{"type": "text", "text": "hi"}]}
        assert detect_error_response(resp) is False

    @pytest.mark.unit
    def test_openai_msg_key_returns_true(self):
        resp = {"msg": "Invalid API key"}
        assert detect_error_response(resp) is True

    @pytest.mark.unit
    def test_openai_error_dict_returns_true(self):
        resp = {"error": {"message": "bad request", "type": "invalid_request_error"}}
        assert detect_error_response(resp) is True

    @pytest.mark.unit
    def test_openai_error_string_returns_true(self):
        resp = {"error": "simple error"}
        assert detect_error_response(resp) is True

    @pytest.mark.unit
    def test_valid_openai_response_returns_false(self):
        resp = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        }
        assert detect_error_response(resp) is False

    @pytest.mark.unit
    def test_empty_dict_returns_false(self):
        assert detect_error_response({}) is False


# ===========================================================================
# extract_error_info
# ===========================================================================


class TestExtractErrorInfo:
    """Tests for the extract_error_info priority chain."""

    @pytest.mark.unit
    def test_none_response(self):
        info = extract_error_info(None)
        assert info.message == "Provider returned None response"
        assert info.code is None

    @pytest.mark.unit
    def test_anthropic_error_dict(self):
        resp = {"type": "error", "error": {"type": "overloaded", "message": "busy"}}
        info = extract_error_info(resp)
        assert info.message == "busy"
        assert info.code == "overloaded"

    @pytest.mark.unit
    def test_anthropic_error_string(self):
        resp = {"type": "error", "error": "raw string"}
        info = extract_error_info(resp)
        assert info.message == "raw string"
        assert info.code is None

    @pytest.mark.unit
    def test_openai_msg_style(self):
        resp = {"msg": "invalid key", "code": 401}
        info = extract_error_info(resp)
        assert info.message == "invalid key"
        assert info.code == 401

    @pytest.mark.unit
    def test_openai_error_dict(self):
        resp = {"error": {"message": "rate limited", "code": "rate_limit"}}
        info = extract_error_info(resp)
        assert info.message == "rate limited"
        assert info.code == "rate_limit"

    @pytest.mark.unit
    def test_openai_error_string(self):
        resp = {"error": "simple message"}
        info = extract_error_info(resp)
        assert info.message == "simple message"
        assert info.code is None


# ===========================================================================
# TokenFieldMap presets
# ===========================================================================


class TestTokenFieldMapPresets:
    """Verify the OPENAI and ANTHROPIC token field presets."""

    @pytest.mark.unit
    def test_openai_token_fields(self):
        assert OPENAI_TOKEN_FIELDS.input_tokens == "prompt_tokens"
        assert OPENAI_TOKEN_FIELDS.output_tokens == "completion_tokens"
        assert OPENAI_TOKEN_FIELDS.cache_read_tokens is None

    @pytest.mark.unit
    def test_anthropic_token_fields(self):
        assert ANTHROPIC_TOKEN_FIELDS.input_tokens == "input_tokens"
        assert ANTHROPIC_TOKEN_FIELDS.output_tokens == "output_tokens"
        assert ANTHROPIC_TOKEN_FIELDS.cache_read_tokens == "cache_read_tokens"


# ===========================================================================
# finalize_nonstreaming_metrics
# ===========================================================================


class TestFinalizeNonstreamingMetrics:
    """Tests for the centralized non-streaming metrics finalization."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_anthropic_response_token_extraction(self):
        """Anthropic response with usage -> correct token counts."""
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()
        ctx = _make_context(metrics=metrics, tracker=tracker)

        response = {
            "id": "msg_123",
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_tokens": 2},
        }

        await finalize_nonstreaming_metrics(
            response=response,
            context=ctx,
            field_map=ANTHROPIC_TOKEN_FIELDS,
            count_tool_calls=False,
        )

        assert metrics.input_tokens == 10
        assert metrics.output_tokens == 5
        assert metrics.cache_read_tokens == 2
        tracker.end_request.assert_awaited_once_with("req-test")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_openai_response_with_tool_calls(self):
        """OpenAI response with tool_calls -> correct tokens + tool_call_count."""
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()
        ctx = _make_context(metrics=metrics, tracker=tracker)

        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "c1"}, {"id": "c2"}],
                    }
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8},
        }

        await finalize_nonstreaming_metrics(
            response=response,
            context=ctx,
            field_map=OPENAI_TOKEN_FIELDS,
            count_tool_calls=True,
        )

        assert metrics.input_tokens == 20
        assert metrics.output_tokens == 8
        assert metrics.tool_call_count == 2
        tracker.end_request.assert_awaited_once_with("req-test")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_metrics_disabled_returns_early(self):
        """When is_metrics_enabled=False, nothing happens — no crash."""
        ctx = _make_context(is_metrics_enabled=False, metrics=None, tracker=None)

        await finalize_nonstreaming_metrics(
            response={"some": "data"},
            context=ctx,
            field_map=OPENAI_TOKEN_FIELDS,
        )
        # No exception = success

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_none_response_zeros_tokens(self):
        """None response -> all token metrics zeroed, tracker still called."""
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()
        ctx = _make_context(metrics=metrics, tracker=tracker)

        await finalize_nonstreaming_metrics(
            response=None,
            context=ctx,
            field_map=ANTHROPIC_TOKEN_FIELDS,
            count_tool_calls=True,
        )

        assert metrics.response_size == 0
        assert metrics.input_tokens == 0
        assert metrics.output_tokens == 0
        assert metrics.cache_read_tokens == 0
        assert metrics.cache_creation_tokens == 0
        assert metrics.tool_call_count == 0
        tracker.end_request.assert_awaited_once_with("req-test")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_usage_dict_defaults_to_zero(self):
        """Response without usage -> token metrics default to 0."""
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()
        ctx = _make_context(metrics=metrics, tracker=tracker)

        response = {"id": "msg_no_usage", "content": []}

        await finalize_nonstreaming_metrics(
            response=response,
            context=ctx,
            field_map=ANTHROPIC_TOKEN_FIELDS,
            count_tool_calls=False,
        )

        assert metrics.input_tokens == 0
        assert metrics.output_tokens == 0
        tracker.end_request.assert_awaited_once_with("req-test")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tracker_none_no_crash(self):
        """tracker=None -> end_request not called, no AttributeError."""
        metrics = MagicMock()
        ctx = _make_context(metrics=metrics, tracker=None)

        await finalize_nonstreaming_metrics(
            response={"usage": {"input_tokens": 5}},
            context=ctx,
            field_map=ANTHROPIC_TOKEN_FIELDS,
        )

        # If we reach here without exception, the guard worked.

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bug_fix_tracker_called_when_log_request_metrics_false(self):
        """BUG FIX: tracker.end_request must be called even when
        config.log_request_metrics is False.

        The old OpenAI handler gated tracker.end_request() behind
        log_request_metrics (a verbose-logging flag), which meant
        requests processed without verbose logging never got recorded
        in the tracker's running totals.  The centralized
        finalize_nonstreaming_metrics fixes this by calling
        tracker.end_request() unconditionally (within the
        is_metrics_enabled guard).
        """
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()
        # log_request_metrics=False simulates verbose logging being off
        ctx = _make_context(
            metrics=metrics,
            tracker=tracker,
            config_log_request_metrics=False,
        )

        response = {"usage": {"input_tokens": 7, "output_tokens": 3}}

        await finalize_nonstreaming_metrics(
            response=response,
            context=ctx,
            field_map=ANTHROPIC_TOKEN_FIELDS,
            count_tool_calls=False,
        )

        # The critical assertion: tracker MUST be called regardless of
        # the log_request_metrics setting.
        tracker.end_request.assert_awaited_once_with("req-test")


# ===========================================================================
# finalize_metrics_on_streaming_error
# ===========================================================================


class TestFinalizeMetricsOnStreamingError:
    """Tests for the streaming error metrics finalization."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_with_metrics_sets_fields_and_ends_request(self):
        tracker = MagicMock()
        tracker.end_request = AsyncMock()
        metrics = MagicMock()

        await finalize_metrics_on_streaming_error(
            metrics=metrics,
            error="connection reset",
            tracker=tracker,
            request_id="req-s1",
        )

        assert metrics.error == "connection reset"
        assert metrics.error_type == ErrorType.API_ERROR
        assert metrics.end_time > 0
        tracker.end_request.assert_awaited_once_with("req-s1")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_without_metrics_returns_early(self):
        """metrics=None -> no crash, tracker not called."""
        tracker = MagicMock()
        tracker.end_request = AsyncMock()

        await finalize_metrics_on_streaming_error(
            metrics=None,
            error="some error",
            tracker=tracker,
            request_id="req-s2",
        )

        tracker.end_request.assert_not_awaited()
