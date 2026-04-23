"""Shared mock factory helpers for RequestOrchestrator tests.

These helpers are used by both the basic orchestrator test suite and the
error-paths test suite.  The error-path extensions (get_client_raises,
get_api_key_raises, resolve_raises) are optional parameters that default
to None, so the basic suite can call these factories without supplying them.

WHY a shared module instead of duplicated locals?
  - Both test files had near-identical copies of 4 factory functions.
  - The error-paths file added extra ``*_raises`` params to the signatures.
  - Merging into one module eliminates drift: a fix in one file no longer
    needs to be manually copied to the other.
  - Callers use the same names either way, so the test bodies stay readable.
"""

from unittest.mock import AsyncMock, MagicMock, Mock


def create_mock_provider_config(
    name: str = "openai",
    uses_passthrough: bool = False,
    uses_oauth: bool = False,
    is_anthropic_format: bool = False,
) -> MagicMock:
    """Create a mock ProviderConfig with explicit boolean defaults.

    MagicMock auto-creates truthy attributes for undefined properties.
    This factory forces every dispatch boolean to False so tests hit the
    intended code path instead of accidentally entering the OAuth branch.

    Background: _prepare_authentication has a three-way dispatch
    (passthrough -> oauth -> api_key).  A bare MagicMock makes every
    attribute truthy, so ``provider_config.uses_oauth`` evaluates as True
    and the OAuth branch returns None before ``get_next_provider_api_key``
    is ever called -- breaking tests that expect a real API key.
    """
    config = MagicMock()
    config.name = name
    config.uses_passthrough = uses_passthrough
    config.uses_oauth = uses_oauth
    config.is_anthropic_format = is_anthropic_format
    return config


def create_mock_provider_manager(
    provider_config: Mock | None = None,
    client: Mock | None = None,
    api_key: str | None = "sk-prov-key",
    has_middleware: bool = False,
    middleware_chain: Mock | None = None,
    get_client_raises: Exception | None = None,
    get_api_key_raises: Exception | None = None,
) -> Mock:
    """Create a mock provider manager with proper attribute control.

    Args:
        provider_config: Mock provider config to return
        client: Mock client to return
        api_key: API key to return from get_next_provider_api_key
        has_middleware: Whether to include middleware_chain attribute
        middleware_chain: Mock middleware chain to use
        get_client_raises: If set, get_client raises this exception
        get_api_key_raises: If set, get_next_provider_api_key raises this exception

    Returns:
        A properly configured mock provider manager
    """
    if has_middleware and middleware_chain is not None:
        # Include middleware_chain in spec_set so hasattr() checks succeed
        pm = Mock(
            spec_set=[
                "get_provider_config",
                "get_client",
                "get_next_provider_api_key",
                "middleware_chain",
            ]
        )
        pm.middleware_chain = middleware_chain
    else:
        # No middleware_chain attribute at all
        pm = Mock(spec_set=["get_provider_config", "get_client", "get_next_provider_api_key"])

    pm.get_provider_config = Mock(return_value=provider_config)

    if get_client_raises:
        pm.get_client = Mock(side_effect=get_client_raises)
    else:
        pm.get_client = Mock(return_value=client)

    if get_api_key_raises:
        pm.get_next_provider_api_key = AsyncMock(side_effect=get_api_key_raises)
    else:
        pm.get_next_provider_api_key = AsyncMock(return_value=api_key)

    return pm


def create_mock_model_manager(
    provider: str = "openai",
    model: str = "gpt-4o",
    resolve_raises: Exception | None = None,
) -> Mock:
    """Create a mock ModelManager.

    Args:
        provider: Provider name to return from resolve_model
        model: Model name to return from resolve_model
        resolve_raises: If set, resolve_model raises this exception

    Returns:
        A mock ModelManager with resolve_model method.
    """
    mm = Mock(spec_set=["resolve_model"])

    if resolve_raises:
        mm.resolve_model = Mock(side_effect=resolve_raises)
    else:
        mm.resolve_model = Mock(return_value=(provider, model))

    return mm


def create_mock_config(
    provider_config: Mock | None = None,
    client: Mock | None = None,
    api_key: str | None = "sk-prov-key",
    has_middleware: bool = False,
    middleware_chain: Mock | None = None,
    log_request_metrics: bool = False,
    get_client_raises: Exception | None = None,
    get_api_key_raises: Exception | None = None,
) -> Mock:
    """Create a mock config with provider_manager and proper delegation.

    The returned mock mirrors the real Config interface that
    RequestOrchestrator expects: ``log_request_metrics``,
    ``provider_manager``, plus delegated client-factory methods
    (``get_provider_config``, ``get_client``, ``get_next_provider_api_key``)
    and an optional ``middleware_chain``.

    Args:
        provider_config: Mock provider config to return
        client: Mock client to return
        api_key: API key to return from get_next_provider_api_key
        has_middleware: Whether to include middleware_chain attribute
        middleware_chain: Mock middleware chain to use
        log_request_metrics: Whether request metrics are enabled
        get_client_raises: If set, get_client raises this exception
        get_api_key_raises: If set, get_next_provider_api_key raises this exception

    Returns:
        A properly configured mock config that delegates to provider_manager
    """
    mock_provider_manager = create_mock_provider_manager(
        provider_config=provider_config,
        client=client,
        api_key=api_key,
        has_middleware=has_middleware,
        middleware_chain=middleware_chain,
        get_client_raises=get_client_raises,
        get_api_key_raises=get_api_key_raises,
    )
    # Build spec_set based on whether middleware is needed
    if has_middleware:
        spec = [
            "log_request_metrics",
            "provider_manager",
            "get_provider_config",
            "get_client",
            "get_next_provider_api_key",
            "middleware_chain",
        ]
    else:
        spec = [
            "log_request_metrics",
            "provider_manager",
            "get_provider_config",
            "get_client",
            "get_next_provider_api_key",
        ]
    mock_config = MagicMock(spec_set=spec)
    mock_config.log_request_metrics = log_request_metrics
    mock_config.provider_manager = mock_provider_manager
    # Delegate client_factory methods to provider_manager
    mock_config.get_provider_config = mock_provider_manager.get_provider_config
    mock_config.get_client = mock_provider_manager.get_client
    mock_config.get_next_provider_api_key = mock_provider_manager.get_next_provider_api_key
    if has_middleware:
        mock_config.middleware_chain = middleware_chain
    return mock_config
