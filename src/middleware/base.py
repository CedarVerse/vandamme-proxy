"""
Base Middleware Infrastructure

Defines the elegant middleware architecture for Vandamme Proxy.

The middleware system follows these principles:
- Immutability: Context objects are immutable dataclasses
- Composability: Middlewares can be stacked and chained
- Asynchronicity: All operations are async-native
- Type Safety: Full type annotations throughout
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestContext:
    """
    Immutable context for request processing.

    Provides all necessary data for middleware to process requests
    while maintaining immutability for thread safety.
    """

    messages: List[Dict[str, Any]]
    provider: str
    model: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    client_api_key: Optional[str] = None  # Client's API key for passthrough

    def with_updates(self, **kwargs: Any) -> "RequestContext":
        """Create a new context with specified fields updated."""
        # Create a new dict with current values, then update with kwargs
        current_values: Dict[str, Any] = {
            "messages": self.messages,
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "metadata": self.metadata.copy(),
            "client_api_key": self.client_api_key,
        }
        current_values.update(kwargs)
        return RequestContext(**current_values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ResponseContext:
    """
    Immutable context for response processing.

    Wraps provider responses with additional metadata for middleware processing.
    """

    response: Dict[str, Any]
    request_context: RequestContext
    is_streaming: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_updates(self, **kwargs: Any) -> "ResponseContext":
        """Create a new context with specified fields updated."""
        current_values: Dict[str, Any] = {
            "response": self.response,
            "request_context": self.request_context,
            "is_streaming": self.is_streaming,
            "metadata": self.metadata.copy(),
        }
        current_values.update(kwargs)
        return ResponseContext(**current_values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class StreamChunkContext:
    """
    Context for individual streaming chunks.

    Used by middleware that need to process streaming responses incrementally.
    """

    delta: Dict[str, Any]
    request_context: RequestContext
    accumulated_metadata: Dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False


class Middleware(ABC):
    """
    Abstract base class for all middleware implementations.

    Each middleware can:
    1. Choose whether to handle a specific provider/model combination
    2. Modify requests before they're sent to the provider
    3. Process responses after they're received
    4. Handle streaming chunks for real-time processing
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging and debugging."""
        pass

    @abstractmethod
    async def should_handle(self, provider: str, model: str) -> bool:
        """
        Determine if this middleware should handle the given provider/model.

        Args:
            provider: The provider name (e.g., "vertex", "openai")
            model: The model name (e.g., "gemini-3-pro")

        Returns:
            True if this middleware should process the request
        """
        pass

    async def before_request(self, context: RequestContext) -> RequestContext:
        """
        Process request before sending to provider.

        Args:
            context: The request context

        Returns:
            Possibly modified request context
        """
        return context

    async def after_response(self, context: ResponseContext) -> ResponseContext:
        """
        Process response after receiving from provider.

        Args:
            context: The response context

        Returns:
            Possibly modified response context
        """
        return context

    async def on_stream_chunk(self, context: StreamChunkContext) -> StreamChunkContext:
        """
        Process individual streaming chunks.

        Args:
            context: The stream chunk context

        Returns:
            Possibly modified stream chunk context
        """
        return context

    async def on_stream_complete(self, context: RequestContext, metadata: Dict[str, Any]) -> None:
        """
        Called when streaming response is complete.

        Args:
            context: The original request context
            metadata: Accumulated metadata from streaming
        """
        pass

    async def initialize(self) -> None:
        """
        Initialize the middleware.

        Called once when the middleware chain is created.
        """
        pass

    async def cleanup(self) -> None:
        """
        Cleanup resources.

        Called during application shutdown.
        """
        pass


class MiddlewareChain:
    """
    Elegant middleware chain orchestrator.

    Manages the execution of middleware in the correct order,
    with proper error handling and performance monitoring.
    """

    def __init__(self) -> None:
        self._middlewares: List[Middleware] = []
        self._initialized = False
        self.logger = logging.getLogger(f"{__name__}.MiddlewareChain")

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """
        Add a middleware to the chain.

        Args:
            middleware: The middleware to add

        Returns:
            Self for method chaining
        """
        self._middlewares.append(middleware)
        self.logger.debug(f"Added middleware: {middleware.name}")
        return self

    async def initialize(self) -> None:
        """Initialize all middleware in the chain."""
        if self._initialized:
            return

        self.logger.info(f"Initializing {len(self._middlewares)} middlewares")

        for middleware in self._middlewares:
            try:
                await middleware.initialize()
                self.logger.debug(f"Initialized middleware: {middleware.name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {middleware.name}: {e}")
                raise

        self._initialized = True
        self.logger.info("Middleware chain initialization complete")

    async def cleanup(self) -> None:
        """Cleanup all middleware in the chain."""
        if not self._initialized:
            return

        self.logger.info("Cleaning up middleware chain")

        # Cleanup in reverse order
        for middleware in reversed(self._middlewares):
            try:
                await middleware.cleanup()
                self.logger.debug(f"Cleaned up middleware: {middleware.name}")
            except Exception as e:
                self.logger.error(f"Error cleaning up {middleware.name}: {e}")

        self._initialized = False

    async def process_request(self, context: RequestContext) -> RequestContext:
        """
        Process request through applicable middleware.

        Args:
            context: The request context

        Returns:
            Processed request context
        """
        if not self._initialized:
            await self.initialize()

        current_context = context
        applicable_middlewares = []

        # Find applicable middleware
        for middleware in self._middlewares:
            if await middleware.should_handle(context.provider, context.model):
                applicable_middlewares.append(middleware)

        if not applicable_middlewares:
            return context

        self.logger.debug(
            f"Processing request through {len(applicable_middlewares)} middlewares, "
            f"provider={context.provider}, model={context.model}, "
            f"middlewares={[m.name for m in applicable_middlewares]}"
        )

        # Execute middleware chain
        for middleware in applicable_middlewares:
            try:
                new_context = await middleware.before_request(current_context)
                if new_context is not current_context:
                    self.logger.debug(f"Request modified by {middleware.name}")
                current_context = new_context
            except Exception as e:
                self.logger.error(
                    f"Error in {middleware.name}.before_request: {e}, "
                    f"provider={context.provider}, model={context.model}"
                )
                raise

        return current_context

    async def process_response(self, context: ResponseContext) -> ResponseContext:
        """
        Process response through applicable middleware.

        Args:
            context: The response context

        Returns:
            Processed response context
        """
        if not self._initialized:
            await self.initialize()

        current_context = context
        applicable_middlewares = []

        # Find applicable middleware
        for middleware in self._middlewares:
            if await middleware.should_handle(
                context.request_context.provider, context.request_context.model
            ):
                applicable_middlewares.append(middleware)

        if not applicable_middlewares:
            return context

        # Execute middleware chain in order
        for middleware in applicable_middlewares:
            try:
                new_context = await middleware.after_response(current_context)
                if new_context is not current_context:
                    self.logger.debug(f"Response modified by {middleware.name}")
                current_context = new_context
            except Exception as e:
                self.logger.error(
                    f"Error in {middleware.name}.after_response: {e}, "
                    f"provider={context.request_context.provider}, "
                    f"model={context.request_context.model}"
                )
                raise

        return current_context

    async def process_stream_chunk(self, context: StreamChunkContext) -> StreamChunkContext:
        """
        Process streaming chunk through applicable middleware.

        Args:
            context: The stream chunk context

        Returns:
            Processed stream chunk context
        """
        if not self._initialized:
            await self.initialize()

        current_context = context
        applicable_middlewares = []

        # Find applicable middleware
        for middleware in self._middlewares:
            if await middleware.should_handle(
                context.request_context.provider, context.request_context.model
            ):
                applicable_middlewares.append(middleware)

        if not applicable_middlewares:
            return context

        # Execute middleware chain
        for middleware in applicable_middlewares:
            try:
                new_context = await middleware.on_stream_chunk(current_context)
                if new_context is not current_context:
                    # Check if chunk was modified
                    if new_context.delta is not context.delta:
                        self.logger.debug(f"Stream chunk modified by {middleware.name}")
                current_context = new_context
            except Exception as e:
                self.logger.error(
                    f"Error in {middleware.name}.on_stream_chunk: {e}, "
                    f"provider={context.request_context.provider}, "
                    f"model={context.request_context.model}"
                )
                raise

        # Notify middleware of completion if this is the last chunk
        if context.is_complete:
            for middleware in applicable_middlewares:
                try:
                    await middleware.on_stream_complete(
                        context.request_context, current_context.accumulated_metadata
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error in {middleware.name}.on_stream_complete: {e}, "
                        f"provider={context.request_context.provider}, "
                        f"model={context.request_context.model}"
                    )

        return current_context
