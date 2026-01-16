"""Protocol definitions for dependency inversion.

This module defines Protocol interfaces (PEP 544) that enable clean
separation of concerns and eliminate circular imports.

Protocols are defined at layer boundaries:
- src/api/ depends on these protocols
- src/core/ implements these protocols
- Dependencies flow downward (no upward circular references)

Benefits:
1. Zero circular imports - protocols break dependency cycles
2. Clean imports - all at module level, no lazy loading
3. Better type safety - mypy validates protocol conformance
4. Easier testing - mock protocols instead of complex concrete classes
5. Clear contracts - protocols document exact interfaces
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConfigProvider(Protocol):
    """Protocol for configuration access.

    Provides read-only access to configuration values used throughout
    the application. This allows components to depend on the protocol
    instead of the concrete Config class.
    """

    @property
    def max_tokens_limit(self) -> int: ...

    @property
    def min_tokens_limit(self) -> int: ...

    @property
    def request_timeout(self) -> int: ...

    @property
    def streaming_read_timeout(self) -> float | None: ...

    @property
    def streaming_connect_timeout(self) -> float: ...

    @property
    def max_retries(self) -> int: ...

    @property
    def log_request_metrics(self) -> bool: ...

    @property
    def proxy_api_key(self) -> str | None: ...

    @property
    def default_provider(self) -> str: ...

    @property
    def base_url(self) -> str: ...

    @property
    def azure_api_version(self) -> str | None: ...

    @property
    def active_requests_sse_enabled(self) -> bool: ...

    @property
    def active_requests_sse_interval(self) -> float: ...

    @property
    def active_requests_sse_heartbeat(self) -> float: ...

    def validate_client_api_key(self, client_api_key: str) -> bool: ...

    def get_custom_headers(self) -> dict[str, str]: ...


@runtime_checkable
class ModelResolver(Protocol):
    """Protocol for model name resolution.

    Handles resolving model aliases and provider prefixes to determine
    the actual provider and model name to use for a request.
    """

    def resolve_model(self, model: str) -> tuple[str, str]:
        """Resolve model name to (provider, actual_model).

        Resolution process:
        1. Apply alias resolution if available
        2. Parse provider prefix from resolved value
        3. Return provider and actual model name

        Returns:
            Tuple[str, str]: (provider_name, actual_model_name)
        """
        ...


@runtime_checkable
class ProviderClientFactory(Protocol):
    """Protocol for creating provider API clients.

    Abstracts the creation of OpenAI/Anthropic clients for different
    providers, allowing the orchestrator to work with any implementation.
    """

    def get_client(self, provider_name: str, client_api_key: str | None = None) -> Any: ...

    def get_provider_config(self, provider_name: str) -> Any: ...

    async def get_next_provider_api_key(self, provider_name: str) -> str: ...

    @property
    def default_provider(self) -> str: ...


@runtime_checkable
class MiddlewareProcessor(Protocol):
    """Protocol for middleware preprocessing.

    Allows the orchestrator to apply middleware transformations
    without depending on concrete middleware implementations.
    """

    async def preprocess_request(
        self,
        provider: str,
        request: Any,
        model: str,
        request_id: str,
        client_api_key: str | None,
    ) -> Any:
        """Apply middleware preprocessing to the request.

        Args:
            provider: The provider name
            request: The OpenAI request dict
            model: The original Claude model name
            request_id: Unique request identifier
            client_api_key: Optional client API key

        Returns:
            The processed request (may be modified)
        """
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """Protocol for metrics collection.

    Provides an abstraction for tracking request metrics without
    depending on the concrete metrics implementation.
    """

    async def initialize_request_metrics(
        self,
        request_id: str,
        model: str,
        provider: str,
        resolved_model: str,
        is_streaming: bool,
    ) -> Any: ...

    async def finalize_metrics(
        self, metrics: Any, response: Any, error: Exception | None
    ) -> None: ...
