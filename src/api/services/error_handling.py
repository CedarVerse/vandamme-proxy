"""Error handling services for API endpoints.

This module provides utilities for handling errors and finalizing metrics
in streaming and non-streaming contexts.
"""

import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any

from fastapi.responses import JSONResponse

from src.core.error_types import ErrorType

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Shared helpers for non-streaming error detection and metrics finalization
#
# These utilities centralize logic that was previously duplicated across
# AnthropicNonStreamingHandler and OpenAINonStreamingHandler.  Pulling them
# into one place ensures consistent error classification and guarantees that
# `tracker.end_request()` is always called (fixing a bug in the OpenAI handler
# where it was gated by `log_request_metrics` instead of `is_metrics_enabled`).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    """Structured representation of a provider error."""

    message: str
    # DECISION: union type because OpenAI returns int HTTP codes (401, 429)
    # while Anthropic returns string error types ("overloaded", "not_found_error").
    # Callers use isinstance(code, int) to pick the right HTTP status.
    code: int | str | None = None


def detect_error_response(response: dict | None) -> bool:
    """Detect whether a provider response represents an error.

    Covers every known upstream error shape:
    Anthropic ``{"type": "error", ...}``, OpenAI ``{"error": ...}``,
    legacy ``{"msg": ...}``, and ``None`` (empty body).

    Args:
        response: The parsed JSON response dict, or ``None``.

    Returns:
        ``True`` if the response signals an error condition.
    """
    if response is None:
        return True
    # GOTCHA: "msg" is not a standard OpenAI field — it comes from older
    # proxies and some non-OpenAI providers. Kept for backward compatibility.
    if response.get("msg") is not None:
        return True
    if response.get("error") is not None:
        return True
    return response.get("type") == "error"


def extract_error_info(response: dict | None) -> ErrorInfo:
    """Extract structured error information from a provider response.

    Priority order matters: Anthropic shapes are checked first (they have
    ``type == "error"`` as an explicit sentinel) before the looser OpenAI
    checks (``error`` key could theoretically appear in non-error responses).

    Args:
        response: The parsed JSON response dict, or ``None``.

    Returns:
        An ``ErrorInfo`` with the extracted message and optional code.
    """
    if response is None:
        return ErrorInfo(message="Provider returned None response")

    # Anthropic-style: {"type": "error", "error": {"message": ..., "type": ...}}
    if response.get("type") == "error" and isinstance(response.get("error"), dict):
        err = response["error"]
        return ErrorInfo(
            message=err.get("message", "Provider error"),
            code=err.get("type"),
        )

    # Anthropic-style: {"type": "error", "error": "some string"}
    if response.get("type") == "error" and isinstance(response.get("error"), str):
        return ErrorInfo(message=response["error"])

    # OpenAI msg style: {"msg": "...", "code": ...}
    if response.get("msg") is not None:
        return ErrorInfo(
            message=response["msg"],
            code=response.get("code"),
        )

    # OpenAI error dict: {"error": {"message": ..., "code": ...}}
    if isinstance(response.get("error"), dict):
        err = response["error"]
        return ErrorInfo(
            message=err.get("message", "Provider error"),
            code=err.get("code"),
        )

    # OpenAI error string: {"error": "some string"}
    if isinstance(response.get("error"), str):
        return ErrorInfo(message=response["error"])

    return ErrorInfo(
        message="Provider error"
    )  # INVARIANT: fallback — should never be reached if detect_error_response returned True


@dataclass(frozen=True, slots=True)
class TokenFieldMap:
    """Maps provider-specific token field names to canonical metric attributes.

    WHY a mapping instead of provider-specific extraction methods:
    At current scale (3 formats) this is the right size. If a 4th format
    arrives with fundamentally different structure (e.g., gRPC metadata),
    refactor then — don't pre-build an adapter pattern.

    A field value of ``None`` means the provider does not report that token type.
    """

    input_tokens: str
    output_tokens: str
    cache_read_tokens: str | None = None
    cache_creation_tokens: str | None = None


# DECISION: preset constants over provider-specific subclasses.
# If a new provider uses novel field names, add a new preset here
# rather than scattering if/else across handlers.

OPENAI_TOKEN_FIELDS = TokenFieldMap(
    input_tokens="prompt_tokens",
    output_tokens="completion_tokens",
    cache_read_tokens=None,  # WHY None: nested under prompt_tokens_details, not top-level
    cache_creation_tokens="cache_creation_tokens",
)

ANTHROPIC_TOKEN_FIELDS = TokenFieldMap(
    input_tokens="input_tokens",
    output_tokens="output_tokens",
    cache_read_tokens="cache_read_tokens",
    cache_creation_tokens="cache_creation_tokens",
)


async def finalize_nonstreaming_metrics(
    *,
    response: dict | None,
    context: Any,  # ApiRequestContext — typed as Any to avoid circular import
    field_map: TokenFieldMap,
    count_tool_calls: bool = True,
) -> None:
    """Finalize request metrics for a non-streaming response.

    INVARIANT: tracker.end_request() is always called (within the
    is_metrics_enabled guard).  Callers depend on this for accurate
    running totals in the dashboard.  The old OpenAI handler gated this
    behind log_request_metrics (a verbose logging flag) — that was a bug.
    """
    # Guard: skip entirely when metrics tracking is disabled.
    if not context.is_metrics_enabled or not context.metrics:
        return

    metrics = context.metrics

    # None response: zero out all counters but still end the request.
    # If we skip tracker.end_request here, the request stays "active" forever.
    if response is None:
        metrics.response_size = 0
        metrics.input_tokens = 0
        metrics.output_tokens = 0
        metrics.cache_read_tokens = 0
        metrics.cache_creation_tokens = 0
        if count_tool_calls:
            metrics.tool_call_count = 0
        if context.tracker is not None:
            await context.tracker.end_request(context.request_id)
        return

    response_json = json.dumps(response)
    metrics.response_size = len(response_json)

    usage = response.get("usage")
    if not usage and getattr(getattr(context, "config", None), "log_request_metrics", False):
        logger.warning("No usage information in response")
    usage = usage or {}

    # Map provider-specific field names to canonical metric attributes.
    # Fields that are None in the map (e.g. OpenAI cache_read_tokens) are
    # skipped — the metric retains its default value of 0.
    for metric_attr, map_field in (
        ("input_tokens", field_map.input_tokens),
        ("output_tokens", field_map.output_tokens),
        ("cache_read_tokens", field_map.cache_read_tokens),
        ("cache_creation_tokens", field_map.cache_creation_tokens),
    ):
        if map_field is not None:
            setattr(metrics, metric_attr, usage.get(map_field, 0))

    if count_tool_calls:
        choices = response.get("choices") or []
        response_message = choices[0].get("message", {}) if choices else {}
        tool_calls = response_message.get("tool_calls") or []
        metrics.tool_call_count = len(tool_calls)

    # INVARIANT: must happen for every tracked request.
    # The tracker uses this to compute running totals (active requests,
    # concurrency, throughput).  Skipping it leaks requests in the dashboard.
    if context.tracker is not None:
        await context.tracker.end_request(context.request_id)
