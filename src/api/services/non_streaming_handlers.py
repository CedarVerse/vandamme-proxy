"""Non-streaming handler services using strategy pattern.

This module provides format-specific non-streaming handlers that encapsulate
the logic for handling non-streaming requests with different API formats.
This eliminates deep nesting in the endpoint by using a strategy pattern.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from src.api.context.request_context import RequestContext as ApiRequestContext
from src.api.services.error_handling import (
    ANTHROPIC_TOKEN_FIELDS,
    OPENAI_TOKEN_FIELDS,
    detect_error_response,
    extract_error_info,
    finalize_nonstreaming_metrics,
)
from src.api.services.key_rotation import build_api_key_params
from src.api.services.request_builder import build_anthropic_passthrough_request
from src.conversion.response_converter import convert_openai_to_claude_response
from src.core.logging import ConversationLogger
from src.middleware import RequestContext, ResponseContext

logger = logging.getLogger(__name__)
conversation_logger = ConversationLogger.get_logger()


class NonStreamingHandler(ABC):
    """Abstract base for format-specific non-streaming handlers.

    Each handler encapsulates the logic for processing non-streaming requests
    in a specific API format (Anthropic or OpenAI).
    """

    @abstractmethod
    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> JSONResponse:
        """Handle a non-streaming request with RequestContext.

        Args:
            context: The ApiRequestContext containing all request data.

        Returns:
            A JSONResponse with the Claude API format response.
        """
        pass


class AnthropicNonStreamingHandler(NonStreamingHandler):
    """Handler for Anthropic-format non-streaming requests.

    This handler processes non-streaming requests for providers that use
    Anthropic-compatible API format (direct passthrough without conversion).
    """

    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> JSONResponse:
        """Handle Anthropic-format non-streaming with direct passthrough."""
        # Get model_manager from app.state
        from src.core.model_manager_runtime import get_model_manager

        model_manager = get_model_manager(context.http_request)
        _resolved_model, claude_request_dict = build_anthropic_passthrough_request(
            request=context.request,
            provider_name=context.provider_name,
            model_manager=model_manager,
        )

        # Make API call
        api_key_params = build_api_key_params(
            provider_config=context.provider_config,
            provider_name=context.provider_name,
            client_api_key=context.client_api_key,
            provider_api_key=context.provider_api_key,
            config=context.config,
        )
        anthropic_response = await context.openai_client.create_chat_completion(
            claude_request_dict,
            context.request_id,
            **api_key_params,
        )

        # Apply middleware to response if configured
        middleware_chain = getattr(context.config.provider_manager, "middleware_chain", None)
        if middleware_chain:
            response_context = ResponseContext(
                response=anthropic_response,
                request_context=RequestContext(
                    messages=claude_request_dict.get("messages", []),
                    provider=context.provider_name,
                    model=context.request.model,
                    request_id=context.request_id,
                ),
                is_streaming=False,
            )
            processed_response = await middleware_chain.process_response(response_context)
            anthropic_response = processed_response.response

        # --- Centralized error detection ---
        # Previously the Anthropic handler had NO error detection — it silently
        # returned upstream errors as HTTP 200.  Now it uses the same detection
        # logic as the OpenAI handler.
        if detect_error_response(anthropic_response):
            error_info = extract_error_info(anthropic_response)
            logger.error(
                f"[{context.request_id}] Provider {context.provider_name} "
                f"returned error: {error_info.message}"
            )
            await finalize_nonstreaming_metrics(
                response=anthropic_response,
                context=context,
                field_map=ANTHROPIC_TOKEN_FIELDS,
                count_tool_calls=False,
            )
            error_code = error_info.code
            raise HTTPException(
                status_code=error_code if isinstance(error_code, int) else 500,
                detail=f"Provider error: {error_info.message}",
            )

        # --- Centralized metrics finalization ---
        # WHY count_tool_calls=False: Anthropic passthrough doesn't use OpenAI's
        # choices[].message.tool_calls structure — tool use is in content blocks.
        await finalize_nonstreaming_metrics(
            response=anthropic_response,
            context=context,
            field_map=ANTHROPIC_TOKEN_FIELDS,
            count_tool_calls=False,
        )

        return JSONResponse(status_code=200, content=anthropic_response)


class OpenAINonStreamingHandler(NonStreamingHandler):
    """Handler for OpenAI-format non-streaming requests.

    This handler processes non-streaming requests for providers that use
    OpenAI-compatible API format (with format conversion).
    """

    async def handle_with_context(
        self,
        context: "ApiRequestContext",
    ) -> JSONResponse:
        """Handle OpenAI-format non-streaming with conversion to Claude format."""
        api_key_params = build_api_key_params(
            provider_config=context.provider_config,
            provider_name=context.provider_name,
            client_api_key=context.client_api_key,
            provider_api_key=context.provider_api_key,
            config=context.config,
        )
        openai_response = await context.openai_client.create_chat_completion(
            context.openai_request,
            context.request_id,
            **api_key_params,
        )

        # Apply middleware to response if configured
        middleware_chain = getattr(context.config.provider_manager, "middleware_chain", None)
        if middleware_chain:
            response_context = ResponseContext(
                response=openai_response,
                request_context=RequestContext(
                    messages=context.openai_request.get("messages", []),
                    provider=context.provider_name,
                    model=context.request.model,
                    request_id=context.request_id,
                    client_api_key=context.client_api_key,
                ),
                is_streaming=False,
            )
            processed_response = await middleware_chain.process_response(response_context)
            openai_response = processed_response.response

        # --- Centralized error detection ---
        # Replaces the old _is_error_response() which only checked "msg" and
        # "error" keys. The centralized version also catches Anthropic-style
        # {"type": "error"} and None responses.
        if detect_error_response(openai_response):
            error_info = extract_error_info(openai_response)
            logger.error(
                f"[{context.request_id}] Provider {context.provider_name} "
                f"returned error: {error_info.message}"
            )
            if context.config.log_request_metrics:
                response_keys = list(openai_response.keys()) if openai_response else []
                logger.error(f"[{context.request_id}] Error response structure: {response_keys}")
            await finalize_nonstreaming_metrics(
                response=openai_response,
                context=context,
                field_map=OPENAI_TOKEN_FIELDS,
                count_tool_calls=True,
            )
            error_code = error_info.code
            raise HTTPException(
                status_code=error_code if isinstance(error_code, int) else 500,
                detail=f"Provider error: {error_info.message}",
            )

        # --- Centralized metrics finalization ---
        # tracker.end_request() is called inside finalize_nonstreaming_metrics,
        # NOT gated by log_request_metrics.  This fixes a bug where the old code
        # only ended the request when verbose logging was on.
        await finalize_nonstreaming_metrics(
            response=openai_response,
            context=context,
            field_map=OPENAI_TOKEN_FIELDS,
            count_tool_calls=True,
        )

        # Convert to Claude format
        claude_response = convert_openai_to_claude_response(
            openai_response,
            context.request,
            tool_name_map_inverse=context.tool_name_map_inverse,
        )

        # Log successful completion (gated by verbose logging, NOT metrics tracking).
        # Token values come from context.metrics (populated above) — single source of truth.
        duration_ms = (time.time() - context.start_time) * 1000
        if context.config.log_request_metrics:
            input_tokens = context.metrics.input_tokens if context.metrics else 0
            output_tokens = context.metrics.output_tokens if context.metrics else 0
            response_size = context.metrics.response_size if context.metrics else 0

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

        return JSONResponse(status_code=200, content=claude_response)


def get_non_streaming_handler(config: Any, provider_config: Any | None) -> NonStreamingHandler:
    """Factory function to get the appropriate non-streaming handler.

    Args:
        config: Application config object.
        provider_config: The provider configuration (may be None).

    Returns:
        The appropriate non-streaming handler for the provider's API format.
    """
    # Three-way dispatch: responses → anthropic → openai (default)
    #
    # The ChatGPT Responses API only supports streaming — it rejects `stream: false`
    # with a 400. Non-streaming callers must be told up-front rather than receiving
    # a cryptic upstream error.
    #
    # TODO (future task): support non-streaming for responses format by forcing
    # streaming internally and accumulating the stream into a single response.
    if provider_config and provider_config.is_responses_format:
        raise ValueError(
            "ChatGPT Responses API requires streaming. "
            "Non-streaming requests are not supported for providers with api_format='responses'. "
            "Configure the client to use streaming, or switch to api_format='openai'."
        )
    if provider_config and provider_config.is_anthropic_format:
        return AnthropicNonStreamingHandler()
    return OpenAINonStreamingHandler()
