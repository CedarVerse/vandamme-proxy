"""Streaming handler services using strategy pattern.

This module provides format-specific streaming handlers that encapsulate
the logic for handling streaming requests with different API formats.
This eliminates deep nesting in the endpoint by using a strategy pattern.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.context.request_context import RequestContext as ApiRequestContext
from src.api.services.error_handling import (
    build_streaming_error_response,
    finalize_metrics_on_streaming_error,
)
from src.api.services.key_rotation import build_api_key_params
from src.api.services.request_builder import build_anthropic_passthrough_request
from src.api.services.streaming import (
    sse_headers,
    streaming_response,
    with_streaming_error_handling,
)
from src.conversion.response_converter import convert_openai_streaming_to_claude
from src.conversion.responses_converter import (
    convert_openai_to_responses_request,
    translate_responses_sse_to_openai,
)
from src.middleware import RequestContext

logger = logging.getLogger(__name__)


class StreamingHandler(ABC):
    """Abstract base for format-specific streaming handlers.

    Each handler encapsulates the logic for processing streaming requests
    in a specific API format (Anthropic or OpenAI).
    """

    @abstractmethod
    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> StreamingResponse | JSONResponse:
        """Handle a streaming request with RequestContext.

        Args:
            context: The ApiRequestContext containing all request data.

        Returns:
            A StreamingResponse with the appropriate stream.
        """
        pass


class AnthropicStreamingHandler(StreamingHandler):
    """Handler for Anthropic-format streaming requests.

    This handler processes streaming requests for providers that use
    Anthropic-compatible API format (direct passthrough without conversion).
    """

    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> StreamingResponse | JSONResponse:
        """Handle Anthropic-format streaming with direct passthrough."""
        # Get model_manager from app.state
        from src.core.model_manager_runtime import get_model_manager

        model_manager = get_model_manager(context.http_request)
        _resolved_model, claude_request_dict = build_anthropic_passthrough_request(
            request=context.request,
            provider_name=context.provider_name,
            model_manager=model_manager,
        )

        try:
            api_key_params = build_api_key_params(
                provider_config=context.provider_config,
                provider_name=context.provider_name,
                client_api_key=context.client_api_key,
                provider_api_key=context.provider_api_key,
                config=context.config,
            )
            anthropic_stream = context.openai_client.create_chat_completion_stream(
                claude_request_dict,
                context.request_id,
                **api_key_params,
            )

            return streaming_response(
                stream=with_streaming_error_handling(
                    original_stream=anthropic_stream,
                    http_request=context.http_request,
                    request_id=context.request_id,
                    provider_name=context.provider_name,
                    metrics_enabled=context.is_metrics_enabled,
                ),
                headers=sse_headers(),
            )
        except (HTTPException, ConnectionError, TimeoutError) as e:
            error_msg = str(e.detail) if isinstance(e, HTTPException) else str(e)
            await finalize_metrics_on_streaming_error(
                metrics=context.metrics,
                error=error_msg,
                tracker=context.tracker,
                request_id=context.request_id,
            )
            return build_streaming_error_response(
                exception=e,
                openai_client=context.openai_client,
                metrics=context.metrics,
                tracker=context.tracker,
                request_id=context.request_id,
            )


class OpenAIStreamingHandler(StreamingHandler):
    """Handler for OpenAI-format streaming requests.

    This handler processes streaming requests for providers that use
    OpenAI-compatible API format (with format conversion).
    """

    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> StreamingResponse | JSONResponse:
        """Handle OpenAI-format streaming with conversion to Claude format."""
        try:
            api_key_params = build_api_key_params(
                provider_config=context.provider_config,
                provider_name=context.provider_name,
                client_api_key=context.client_api_key,
                provider_api_key=context.provider_api_key,
                config=context.config,
            )
            openai_stream = context.openai_client.create_chat_completion_stream(
                context.openai_request,
                context.request_id,
                **api_key_params,
            )

            # Convert OpenAI SSE to Claude format
            converted_stream = convert_openai_streaming_to_claude(
                openai_stream,
                context.request,
                logger,
                tool_name_map_inverse=context.tool_name_map_inverse,
                http_request=context.http_request,
                openai_client=context.openai_client,
                request_id=context.request_id,
                metrics=context.metrics,
                enable_usage_tracking=context.is_metrics_enabled,
            )

            stream_with_error_handling = with_streaming_error_handling(
                original_stream=converted_stream,
                http_request=context.http_request,
                request_id=context.request_id,
                provider_name=context.provider_name,
                metrics_enabled=context.is_metrics_enabled,
            )

            # Apply middleware to streaming deltas if configured
            middleware_chain = getattr(context.config.provider_manager, "middleware_chain", None)
            if middleware_chain:
                from src.api.middleware_integration import (
                    MiddlewareAwareRequestProcessor,
                    MiddlewareStreamingWrapper,
                )

                processor = MiddlewareAwareRequestProcessor()
                processor.middleware_chain = middleware_chain

                wrapped_stream = MiddlewareStreamingWrapper(
                    original_stream=stream_with_error_handling,
                    request_context=RequestContext(
                        messages=context.openai_request.get("messages", []),
                        provider=context.provider_name,
                        model=context.request.model,
                        request_id=context.request_id,
                        conversation_id=None,
                        client_api_key=context.client_api_key,
                    ),
                    processor=processor,
                )

                return streaming_response(stream=wrapped_stream, headers=sse_headers())

            return streaming_response(stream=stream_with_error_handling, headers=sse_headers())
        except (HTTPException, ConnectionError, TimeoutError) as e:
            error_msg = str(e.detail) if isinstance(e, HTTPException) else str(e)
            await finalize_metrics_on_streaming_error(
                metrics=context.metrics,
                error=error_msg,
                tracker=context.tracker,
                request_id=context.request_id,
            )
            return build_streaming_error_response(
                exception=e,
                openai_client=context.openai_client,
                metrics=context.metrics,
                tracker=context.tracker,
                request_id=context.request_id,
            )


class ResponsesStreamingHandler(StreamingHandler):
    """Handler for ChatGPT Responses API streaming requests.

    Pipeline (see responses_converter.py for full rationale):

        Claude request
            → [request_converter]              (already done by the endpoint)
            → convert_openai_to_responses_request()
            → ResponsesAPIClient.stream_responses()
            → translate_responses_sse_to_openai()
            → convert_openai_streaming_to_claude()
            → with_streaming_error_handling()

    The Responses API *only* supports streaming, so non-streaming callers are
    rejected earlier in the pipeline (non_streaming_handlers.py).

    Design choice — two-step conversion rather than a direct Responses→Claude
    translator: this keeps the translation chain composable and leverages the
    already-tested OpenAI→Claude state machine without reimplementing it.
    """

    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> "StreamingResponse | JSONResponse":
        """Handle Responses-API streaming via two-step SSE translation."""
        try:
            # Step 1: Convert the already OpenAI-formatted request to Responses API format.
            # context.openai_request was produced by request_converter.convert_claude_to_openai()
            # and contains OpenAI Chat Completions fields (messages, model, tools, …).
            responses_request = convert_openai_to_responses_request(context.openai_request)

            # Step 2: Stream raw SSE from the Responses API.
            # context.openai_client is a ResponsesAPIClient when is_responses_format is True
            # (guaranteed by ClientFactory — see test_responses_client.py).
            #
            # IMPORTANT: The generator is lazy — HTTP errors (400, 401, 403) from
            # the ChatGPT API only fire when the first chunk is consumed.  We eagerly
            # fetch the first line here so that pre-stream errors (wrong model name,
            # expired token, missing instructions) are caught by the except block
            # below and surfaced as a proper error response, instead of silently
            # producing an empty stream inside the already-started StreamingResponse.
            raw_stream_gen = context.openai_client.stream_responses(
                responses_request,
                context.request_id,
            )
            try:
                first_line = await raw_stream_gen.__anext__()
            except StopAsyncIteration:
                # Empty stream — still return a valid (empty) streaming response
                first_line = "data: [DONE]"

            async def _prepend_first_line(
                first: str, rest: AsyncGenerator[str, None]
            ) -> AsyncGenerator[str, None]:
                yield first
                async for line in rest:
                    yield line

            raw_stream = _prepend_first_line(first_line, raw_stream_gen)

            # Step 3: Translate Responses API SSE → OpenAI Chat Completions SSE.
            openai_sse_stream = translate_responses_sse_to_openai(
                raw_stream,
                model=context.resolved_model,
                request_id=context.request_id,
            )

            # Step 4: Translate OpenAI SSE → Claude SSE using the existing converter.
            # Passing tool_name_map_inverse preserves tool name sanitization round-trips.
            converted_stream = convert_openai_streaming_to_claude(
                openai_sse_stream,
                context.request,
                logger,
                tool_name_map_inverse=context.tool_name_map_inverse,
                http_request=context.http_request,
                openai_client=context.openai_client,
                request_id=context.request_id,
                metrics=context.metrics,
                enable_usage_tracking=context.is_metrics_enabled,
            )

            # Step 5: Wrap with error handling and metrics finalisation.
            stream_with_error_handling = with_streaming_error_handling(
                original_stream=converted_stream,
                http_request=context.http_request,
                request_id=context.request_id,
                provider_name=context.provider_name,
                metrics_enabled=context.is_metrics_enabled,
            )

            return streaming_response(stream=stream_with_error_handling, headers=sse_headers())

        except (HTTPException, ConnectionError, TimeoutError) as e:
            error_msg = str(e.detail) if isinstance(e, HTTPException) else str(e)
            await finalize_metrics_on_streaming_error(
                metrics=context.metrics,
                error=error_msg,
                tracker=context.tracker,
                request_id=context.request_id,
            )
            return build_streaming_error_response(
                exception=e,
                openai_client=context.openai_client,
                metrics=context.metrics,
                tracker=context.tracker,
                request_id=context.request_id,
            )


def get_streaming_handler(config: Any, provider_config: Any | None) -> StreamingHandler:
    """Factory function to get the appropriate streaming handler.

    Args:
        config: Application config object.
        provider_config: The provider configuration (may be None).

    Returns:
        The appropriate streaming handler for the provider's API format.
    """
    # Three-way dispatch: responses → anthropic → openai (default).
    # The order matters: is_responses_format must be checked before
    # is_anthropic_format because they are mutually exclusive but both
    # could theoretically match a misconfigured provider.
    if provider_config and provider_config.is_responses_format:
        return ResponsesStreamingHandler()
    if provider_config and provider_config.is_anthropic_format:
        return AnthropicStreamingHandler()
    return OpenAIStreamingHandler()
