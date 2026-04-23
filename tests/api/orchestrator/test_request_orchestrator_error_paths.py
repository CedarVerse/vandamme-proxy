"""Error path tests for RequestOrchestrator.

This module tests error handling and edge cases in the RequestOrchestrator
that are not covered in the basic test suite.

Test Categories:
    1. Provider Resolution Errors - Unknown providers, invalid models
    2. Request Conversion Errors - Conversion failures
    3. Authentication Failures - API key issues, provider not configured
    4. Client Retrieval Errors - Unknown provider, init failures
    5. Metrics Tracker Failures - Tracker not configured, operation failures
    6. Middleware Exception Handling - Middleware raises, malformed context
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.orchestrator.request_orchestrator import RequestOrchestrator
from src.models.claude import ClaudeMessagesRequest

from .helpers import (
    create_mock_config,
    create_mock_model_manager,
    create_mock_provider_config,
    create_mock_provider_manager,
)

# =============================================================================
# Local helpers (only used in this file)
# =============================================================================


def _create_base_request() -> ClaudeMessagesRequest:
    """Create a basic ClaudeMessagesRequest for testing."""
    return ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )


# =============================================================================
# Category 1: Provider Resolution Errors (4 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_provider_resolution_failure_unknown_provider() -> None:
    """Test orchestrator handles unknown provider from model resolution."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    # Model manager raises exception for unknown provider
    mock_model_manager = create_mock_model_manager(
        resolve_raises=ValueError("Unknown provider: 'unknown_provider'")
    )

    mock_config = MagicMock(log_request_metrics=False)

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with pytest.raises(ValueError) as exc_info:
        await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

    assert "Unknown provider" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_provider_resolution_invalid_model_format() -> None:
    """Test orchestrator handles invalid model format (empty string)."""
    request = ClaudeMessagesRequest(
        model="",  # Empty model name
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_model_manager = create_mock_model_manager(
        resolve_raises=ValueError("Model name cannot be empty")
    )

    mock_config = MagicMock(log_request_metrics=False)

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with pytest.raises(ValueError) as exc_info:
        await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

    assert "empty" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_provider_resolution_malformed_prefix() -> None:
    """Test orchestrator handles malformed provider prefix."""
    request = ClaudeMessagesRequest(
        model="::doublecolon",  # Malformed prefix
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_model_manager = create_mock_model_manager(
        resolve_raises=ValueError("Invalid model format: '::doublecolon'")
    )

    mock_config = MagicMock(log_request_metrics=False)

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with pytest.raises(ValueError) as exc_info:
        await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

    assert "Invalid model format" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_provider_config_is_none() -> None:
    """Test orchestrator handles None provider config from get_provider_config."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    # Model manager returns provider name, but provider config is None
    mock_model_manager = create_mock_model_manager(provider="unknown", model="gpt-4o")

    # Provider manager returns None for this provider
    mock_config = create_mock_config(provider_config=None)

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "unknown",
        }

        # The RequestContextBuilder now validates provider_config is not None
        # This test verifies that None provider_config causes a clear error
        with pytest.raises(ValueError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "provider_config" in str(exc_info.value)


# =============================================================================
# Category 2: Request Conversion Errors (3 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_request_conversion_pipeline_failure() -> None:
    """Test orchestrator handles conversion pipeline transformer failure."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        # Conversion raises exception (e.g., from TokenLimitTransformer)
        mock_convert.side_effect = ValueError("max_tokens exceeds limit")

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "max_tokens" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_request_conversion_invalid_tool_schema() -> None:
    """Test orchestrator handles conversion errors during tool schema transformation."""
    # Create a valid request with tools
    from src.models.claude import ClaudeTool

    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
        tools=[
            ClaudeTool(
                name="test_tool",
                description="A test tool",
                input_schema={"type": "object", "properties": {}},
            )
        ],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        # Conversion fails due to tool schema transformation error
        mock_convert.side_effect = ValueError("Tool schema transformation failed: invalid type")

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "transformation" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_request_conversion_missing_required_fields() -> None:
    """Test orchestrator handles conversion result missing required fields."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        # Conversion returns dict without required 'model' field
        mock_convert.return_value = {
            "messages": [{"role": "user", "content": "Hello"}],
            # Missing 'model' field
        }

        # Should handle missing fields gracefully or raise error
        # Current behavior: continues, downstream code may fail
        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        # OpenAI request is set even with missing fields
        assert ctx.openai_request is not None


# =============================================================================
# Category 3: Authentication Failures (3 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_auth_provider_not_configured() -> None:
    """Test orchestrator handles provider not configured for API key retrieval."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config(name="unconfigured")

    # get_next_provider_api_key raises ValueError for unconfigured provider
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        get_api_key_raises=ValueError("Provider 'unconfigured' has no API keys configured"),
    )

    mock_model_manager = create_mock_model_manager(provider="unconfigured")
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "unconfigured",
        }

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "no API keys" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_auth_empty_api_key_list() -> None:
    """Test orchestrator handles provider with empty API key list."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config(name="empty_keys")

    # get_next_provider_api_key raises for empty key list
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        get_api_key_raises=ValueError("Provider 'empty_keys' has no API keys configured"),
    )

    mock_model_manager = create_mock_model_manager(provider="empty_keys")
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "empty_keys",
        }

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "no API keys" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_auth_rotation_failure() -> None:
    """Test orchestrator handles API key rotation failure."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config(name="rotation_fail")

    # get_next_provider_api_key raises during rotation
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        get_api_key_raises=RuntimeError("API key rotation failed"),
    )

    mock_model_manager = create_mock_model_manager(provider="rotation_fail")
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "rotation_fail",
        }

        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "rotation" in str(exc_info.value).lower()


# =============================================================================
# Category 4: Client Retrieval Errors (2 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_client_retrieval_unknown_provider() -> None:
    """Test orchestrator handles get_client for unknown provider."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    # get_client raises ValueError for unknown provider
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        get_client_raises=ValueError("Provider 'unknown' not found"),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        with patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ):
            with pytest.raises(ValueError) as exc_info:
                await orchestrator.prepare_request_context(
                    request=request,
                    http_request=mock_http_request,
                    client_api_key=None,
                )

            assert "not found" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_client_initialization_failure() -> None:
    """Test orchestrator handles client initialization failure."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    # get_client raises due to invalid config (e.g., bad base URL)
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        get_client_raises=ValueError("Invalid base URL: 'not-a-url'"),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        with patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ):
            with pytest.raises(ValueError) as exc_info:
                await orchestrator.prepare_request_context(
                    request=request,
                    http_request=mock_http_request,
                    client_api_key=None,
                )

            assert "base URL" in str(exc_info.value)


# =============================================================================
# Category 5: Metrics Tracker Failures (3 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_metrics_tracker_not_configured() -> None:
    """Test orchestrator handles RequestTracker not configured on app.state."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_provider_config = create_mock_provider_config()

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        log_request_metrics=True,
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch("src.api.orchestrator.request_orchestrator.get_request_tracker") as mock_get_tracker:
        # get_request_tracker returns None (not configured)
        mock_get_tracker.return_value = None

        with patch(
            "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
        ) as mock_convert:
            mock_convert.return_value = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
                "_provider": "openai",
            }

            # Should handle None tracker gracefully
            # Current behavior: may raise AttributeError
            with pytest.raises(AttributeError):
                await orchestrator.prepare_request_context(
                    request=request,
                    http_request=mock_http_request,
                    client_api_key=None,
                )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_metrics_start_request_failure() -> None:
    """Test orchestrator handles tracker.start_request failure."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_tracker = MagicMock()
    mock_tracker.start_request = AsyncMock(side_effect=RuntimeError("Tracker service unavailable"))

    mock_config = MagicMock(
        log_request_metrics=True,
        provider_manager=create_mock_provider_manager(
            provider_config=create_mock_provider_config(),
            client=MagicMock(),
        ),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch(
            "src.api.orchestrator.request_orchestrator.get_request_tracker",
            return_value=mock_tracker,
        ),
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
    ):
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        with pytest.raises(RuntimeError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "unavailable" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_metrics_update_last_accessed_failure() -> None:
    """Test orchestrator handles tracker.update_last_accessed failure."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_tracker = MagicMock()
    mock_metrics = MagicMock(start_time_iso="2024-01-01T00:00:00Z", tool_result_count=0)
    mock_tracker.start_request = AsyncMock(return_value=mock_metrics)
    # update_last_accessed in _initialize_metrics fails
    mock_tracker.update_last_accessed = AsyncMock(side_effect=OSError("Database connection lost"))

    mock_config = MagicMock(
        log_request_metrics=True,
        provider_manager=create_mock_provider_manager(
            provider_config=create_mock_provider_config(),
            client=MagicMock(),
        ),
    )

    mock_model_manager = create_mock_model_manager()
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch(
            "src.api.orchestrator.request_orchestrator.get_request_tracker",
            return_value=mock_tracker,
        ),
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
    ):
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        with pytest.raises(IOError) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert "connection lost" in str(exc_info.value)


# =============================================================================
# Category 6: Middleware Exception Handling (2 tests)
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_middleware_raises_exception() -> None:
    """Test orchestrator handles middleware.process_request raising exception."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    # Mock middleware chain that raises exception
    mock_middleware_chain = MagicMock()
    mock_middleware_chain.process_request = AsyncMock(
        side_effect=ValueError("Middleware processing failed")
    )

    mock_provider_config = create_mock_provider_config(name="gemini")

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="gemini-key",
        has_middleware=True,
        middleware_chain=mock_middleware_chain,
    )

    mock_model_manager = create_mock_model_manager(provider="gemini")
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        mock_convert.return_value = {
            "model": "gemini-2.0-flash",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "gemini",
        }

        with patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ):
            # Middleware exception should propagate
            with pytest.raises(ValueError) as exc_info:
                await orchestrator.prepare_request_context(
                    request=request,
                    http_request=mock_http_request,
                    client_api_key=None,
                )

            assert "Middleware" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_middleware_returns_malformed_context() -> None:
    """Test orchestrator handles middleware returning malformed context."""
    request = _create_base_request()

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    # Mock middleware that returns malformed context (missing messages)
    from src.middleware import RequestContext as MiddlewareRequestContext

    mock_middleware_chain = MagicMock()
    mock_middleware_chain.process_request = AsyncMock(
        return_value=MiddlewareRequestContext(
            messages=None,  # Malformed: None instead of list
            provider="gemini",
            model=request.model,
            request_id="test-123",
            conversation_id=None,
            client_api_key=None,
        )
    )

    mock_provider_config = create_mock_provider_config(name="gemini")

    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="gemini-key",
        has_middleware=True,
        middleware_chain=mock_middleware_chain,
    )

    mock_model_manager = create_mock_model_manager(provider="gemini")
    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with patch(
        "src.api.orchestrator.request_orchestrator.convert_claude_to_openai"
    ) as mock_convert:
        original_messages = [{"role": "user", "content": "Hello"}]
        mock_convert.return_value = {
            "model": "gemini-2.0-flash",
            "messages": original_messages,
            "_provider": "gemini",
        }

        with patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ):
            # Should handle None messages (current behavior: assigns None)
            ctx = await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

            # Messages were replaced with None
            assert ctx.openai_messages is None or ctx.openai_messages == []
