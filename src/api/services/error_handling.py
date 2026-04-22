"""Error handling services for API endpoints.

This module provides utilities for handling errors and finalizing metrics
in streaming and non-streaming contexts.
"""

import logging
import traceback
from dataclasses import dataclass
from typing import Any

from fastapi.responses import JSONResponse

from src.core.error_types import ErrorType
from src.core.logging import ConversationLogger

logger = logging.getLogger(__name__)
conversation_logger = ConversationLogger.get_logger()


@dataclass(frozen=True, slots=True)
class ErrorResponseBuilder:
    """Centralized builder for consistent error responses across all endpoints.

    Provides type-safe methods for constructing error responses with
    consistent structure and status codes.

    Error response format:
    {
        "type": "error",
        "error": {
            "type": "<error_type>",
            "message": "<error_message>"
        }
    }
    """

    @staticmethod
    def not_found(resource: str, identifier: str) -> JSONResponse:
        """Build a 404 Not Found error response.

        Args:
            resource: The type of resource that was not found (e.g., "Provider", "Model")
            identifier: The specific identifier that was not found

        Returns:
            JSONResponse with 404 status and error details
        """
        message = f"{resource} '{identifier}' not found"
        return JSONResponse(
            status_code=404,
            content={
                "type": "error",
                "error": {
                    "type": "not_found",
                    "message": message,
                },
            },
        )

    @staticmethod
    def invalid_parameter(name: str, reason: str, value: Any | None = None) -> JSONResponse:
        """Build a 400 Bad Request error response for invalid parameters.

        Args:
            name: The parameter name that is invalid
            reason: Description of why the parameter is invalid
            value: Optional invalid value (will be converted to string)

        Returns:
            JSONResponse with 400 status and error details
        """
        message = f"Invalid parameter '{name}': {reason}"
        if value is not None:
            message += f" (got: {value!r})"
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_parameter",
                    "message": message,
                },
            },
        )

    @staticmethod
    def unauthorized(message: str = "Authentication required") -> JSONResponse:
        """Build a 401 Unauthorized error response.

        Args:
            message: Optional custom error message

        Returns:
            JSONResponse with 401 status and error details
        """
        return JSONResponse(
            status_code=401,
            content={
                "type": "error",
                "error": {
                    "type": "unauthorized",
                    "message": message,
                },
            },
        )

    @staticmethod
    def forbidden(message: str = "Access denied") -> JSONResponse:
        """Build a 403 Forbidden error response.

        Args:
            message: Optional custom error message

        Returns:
            JSONResponse with 403 status and error details
        """
        return JSONResponse(
            status_code=403,
            content={
                "type": "error",
                "error": {
                    "type": "forbidden",
                    "message": message,
                },
            },
        )

    @staticmethod
    def upstream_error(exception: Exception, context: str | None = None) -> JSONResponse:
        """Build a 502 Bad Gateway or 504 Gateway Timeout error response.

        Automatically detects timeout errors and returns appropriate status code.

        Args:
            exception: The upstream exception
            context: Optional context about what operation failed

        Returns:
            JSONResponse with appropriate status code and error details
        """
        import httpx

        # Detect timeout errors
        if isinstance(exception, httpx.TimeoutException):
            message = "Upstream request timed out"
            if context:
                message += f" while {context}"
            message += ". Consider increasing REQUEST_TIMEOUT."
            return JSONResponse(
                status_code=504,
                content={
                    "type": "error",
                    "error": {
                        "type": "upstream_timeout",
                        "message": message,
                    },
                },
            )

        # Generic upstream error
        message = "Upstream service error"
        if context:
            message += f" while {context}"
        return JSONResponse(
            status_code=502,
            content={
                "type": "error",
                "error": {
                    "type": "upstream_error",
                    "message": message,
                    "details": str(exception),
                },
            },
        )

    @staticmethod
    def internal_error(
        message: str, error_type: str = "internal_error", details: Any | None = None
    ) -> JSONResponse:
        """Build a 500 Internal Server Error response.

        Args:
            message: Human-readable error message
            error_type: Specific error type for classification
            details: Optional additional error details

        Returns:
            JSONResponse with 500 status and error details
        """
        content: dict[str, Any] = {
            "type": "error",
            "error": {
                "type": error_type,
                "message": message,
            },
        }
        if details is not None:
            content["error"]["details"] = details
        return JSONResponse(status_code=500, content=content)

    @staticmethod
    def service_unavailable(message: str = "Service temporarily unavailable") -> JSONResponse:
        """Build a 503 Service Unavailable error response.

        Args:
            message: Optional custom error message

        Returns:
            JSONResponse with 503 status and error details
        """
        return JSONResponse(
            status_code=503,
            content={
                "type": "error",
                "error": {
                    "type": "service_unavailable",
                    "message": message,
                },
            },
        )


async def finalize_metrics_on_streaming_error(
    *,
    metrics: Any | None,
    error: str,
    tracker: Any,
    request_id: str,
) -> None:
    """Finalize metrics when a streaming error occurs.

    Args:
        metrics: The metrics object to update (may be None if disabled).
        error: The error message to record.
        tracker: The request tracker for ending the request.
        request_id: The unique request identifier.
    """
    if metrics:
        metrics.error = error
        metrics.error_type = ErrorType.API_ERROR
        metrics.end_time = __import__("time").time()
        await tracker.end_request(request_id)


def _log_traceback(log: Any = logger) -> None:
    """Log full traceback for debugging.

    This utility centralizes the traceback logging pattern.

    Args:
        log: The logger to use (defaults to module logger).
    """
    log.error(traceback.format_exc())


# =============================================================================
# Shared Non-Streaming Response Helpers
# =============================================================================


def detect_error_response(response: dict[str, Any]) -> bool:
    """Check if a provider response is an error response.

    Compatible with both OpenAI-style {msg, code} errors and
    Anthropic-style {error: {...}} error structures.

    Args:
        response: The raw provider response dict.

    Returns:
        True if the response is an error, False otherwise.
    """
    if response.get("msg") is not None:
        return True
    return response.get("error") is not None


def extract_error_info(response: dict[str, Any]) -> tuple[str, int | None]:
    """Extract error message and code from an error response.

    Compatible with both OpenAI-style {msg, code} errors and
    Anthropic-style {error: {message, code}} error structures.

    Args:
        response: The raw provider error response dict.

    Returns:
        Tuple of (error_message, error_code). code may be None if not present.
    """
    # OpenAI-style: {"msg": "...", "code": 400}
    if response.get("msg") is not None:
        return response.get("msg", "Provider error"), response.get("code")

    # Anthropic-style: {"error": {"message": "...", "code": ...}}
    error_val = response.get("error")
    if error_val is not None:
        if isinstance(error_val, dict):
            return error_val.get("message", "Provider error"), error_val.get("code")
        return str(error_val), None

    return "Provider error", None


async def finalize_nonstreaming_metrics(
    *,
    context: Any,
    response: dict[str, Any],
) -> None:
    """Update metrics and end request tracker for non-streaming responses.

    Extracts usage from OpenAI-format responses (prompt_tokens/completion_tokens)
    and updates context.metrics with response_size, token counts, and cache tokens.

    Args:
        context: RequestContext with metrics, tracker, config, etc.
        response: The raw provider response dict.
    """
    import json
    import time

    response_json = json.dumps(response)
    response_size = len(response_json)

    usage = response.get("usage")
    if usage is None:
        input_tokens = 0
        output_tokens = 0
        if context.config.log_request_metrics:
            conversation_logger.warning("No usage information in response")
    else:
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

    # Count tool calls in response
    choices = response.get("choices") or []
    response_message = choices[0].get("message", {}) if choices else {}
    tool_calls = response_message.get("tool_calls", []) or []
    tool_call_count = len(tool_calls)

    # Update metrics
    if context.is_metrics_enabled and context.metrics:
        context.metrics.response_size = response_size
        context.metrics.input_tokens = input_tokens
        context.metrics.output_tokens = output_tokens
        context.metrics.cache_creation_tokens = (
            usage.get("cache_creation_tokens", 0) if usage else 0
        )
        context.metrics.tool_call_count = tool_call_count

        # Debug logging
        conversation_logger.debug(f"📡 RESPONSE STRUCTURE: {list(response.keys())}")
        conversation_logger.debug(f"📡 FULL RESPONSE: {response}")

    # Log successful completion
    duration_ms = (time.time() - context.start_time) * 1000
    if context.config.log_request_metrics:
        tool_call_display = ""
        if context.metrics and context.metrics.tool_call_count > 0:
            tool_call_display = f" | Tool Calls: {context.metrics.tool_call_count}"
        elif context.tool_use_count > 0 or context.tool_result_count > 0:
            tool_call_display = (
                f" | Tool Uses: {context.tool_use_count} | "
                f"Tool Results: {context.tool_result_count}"
            )

        conversation_logger.info(
            f"✅ SUCCESS | Duration: {duration_ms:.0f}ms | "
            f"Tokens: {input_tokens:,}→{output_tokens:,} | "
            f"Size: {context.request_size:,}→{response_size:,} bytes"
            f"{tool_call_display}"
        )
        await context.tracker.end_request(context.request_id)


# =============================================================================
# Shared Non-Streaming Response Processing
# =============================================================================


def build_streaming_error_response(
    *,
    exception: Exception,
    openai_client: Any,
    metrics: Any | None,
    tracker: Any,
    request_id: str,
) -> JSONResponse:
    """Build standardized error response for streaming failures.

    This function handles HTTPException errors that occur during streaming,
    finalizes metrics, and returns a properly formatted error response.

    Args:
        exception: The HTTPException that occurred.
        openai_client: The OpenAI client for error classification.
        metrics: The metrics object to update (may be None if disabled).
        tracker: The request tracker for ending the request.
        request_id: The unique request identifier.

    Returns:
        A JSONResponse with the error details.
    """
    # Finalize metrics
    if metrics:
        metrics.error = exception.detail if hasattr(exception, "detail") else str(exception)
        metrics.error_type = ErrorType.API_ERROR
        metrics.end_time = __import__("time").time()
        # Note: We can't await here because this is a sync function

    logger.error(
        f"Streaming error: {exception.detail if hasattr(exception, 'detail') else exception}"
    )
    _log_traceback()

    error_message = openai_client.classify_openai_error(
        exception.detail if hasattr(exception, "detail") else str(exception)
    )
    error_response = {
        "type": "error",
        "error": {"type": "api_error", "message": error_message},
    }
    status_code = exception.status_code if hasattr(exception, "status_code") else 500
    return JSONResponse(status_code=status_code, content=error_response)
