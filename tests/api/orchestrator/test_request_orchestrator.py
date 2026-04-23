"""Tests for RequestOrchestrator."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.orchestrator.request_orchestrator import RequestOrchestrator
from src.models.claude import ClaudeMessagesRequest

from .helpers import (
    create_mock_config,
    create_mock_model_manager,
    create_mock_provider_config,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_prepares_basic_context() -> None:
    """Test that orchestrator can prepare a basic RequestContext."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    # Create mock config with provider_manager
    mock_provider_config = create_mock_provider_config()
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="sk-prov-key",
        has_middleware=False,
        log_request_metrics=False,
    )

    mock_model_manager = create_mock_model_manager()

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
    ):
        # Setup mocks
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        assert ctx.request_id is not None
        assert ctx.provider_name == "openai"
        assert ctx.resolved_model == "gpt-4o"
        assert ctx.is_metrics_enabled is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_with_metrics_enabled() -> None:
    """Test that orchestrator initializes metrics when enabled."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)
    # Set up app.state with proper request_tracker to satisfy get_request_tracker
    from src.core.metrics import create_request_tracker

    mock_http_request.app = MagicMock()
    mock_http_request.app.state.request_tracker = create_request_tracker()

    mock_tracker = MagicMock()
    mock_metrics = MagicMock(start_time_iso="2024-01-01T00:00:00Z", tool_result_count=0)
    mock_tracker.start_request = AsyncMock(return_value=mock_metrics)
    mock_tracker.update_last_accessed = AsyncMock()
    mock_tracker.end_request = AsyncMock()

    # Create mock config with provider_manager
    mock_provider_config = create_mock_provider_config()
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="sk-prov-key",
        has_middleware=False,
        log_request_metrics=True,
    )

    mock_model_manager = create_mock_model_manager()

    with (
        patch(
            "src.api.orchestrator.request_orchestrator.get_request_tracker",
            return_value=mock_tracker,
        ),
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ),
    ):
        # Import RequestOrchestrator AFTER patches are applied to ensure proper patching
        from src.api.orchestrator.request_orchestrator import RequestOrchestrator

        orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        assert ctx.is_metrics_enabled is True
        assert ctx.metrics is not None
        assert ctx.tracker is not None
        mock_tracker.start_request.assert_called_once()
        mock_tracker.update_last_accessed.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_passthrough_validation_requires_client_key() -> None:
    """Test that orchestrator raises error when passthrough requires client API key."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)

    # Create mock config with provider_manager for passthrough provider
    mock_provider_config = create_mock_provider_config(
        name="anthropic",
        uses_passthrough=True,
        is_anthropic_format=True,
    )
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key=None,
        has_middleware=False,
        log_request_metrics=False,
    )

    mock_model_manager = create_mock_model_manager(
        provider="anthropic", model="claude-3-5-sonnet-20241022"
    )

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ),
    ):
        mock_convert.return_value = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "anthropic",
        }

        with pytest.raises(HTTPException) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,  # No client key provided
            )

        assert exc_info.value.status_code == 401
        assert "passthrough" in exc_info.value.detail.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_client_disconnect_before_processing() -> None:
    """Test that orchestrator handles client disconnection."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    # Simulate client is disconnected
    mock_http_request.is_disconnected = AsyncMock(return_value=True)

    mock_tracker = MagicMock()
    mock_metrics = MagicMock(start_time_iso="2024-01-01T00:00:00Z", tool_result_count=0)
    mock_tracker.start_request = AsyncMock(return_value=mock_metrics)
    mock_tracker.update_last_accessed = AsyncMock()
    mock_tracker.end_request = AsyncMock()

    # Create mock config with provider_manager
    mock_provider_config = create_mock_provider_config()
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="sk-prov-key",
        has_middleware=False,
        log_request_metrics=True,
    )

    mock_model_manager = create_mock_model_manager()

    with (
        patch(
            "src.api.orchestrator.request_orchestrator.get_request_tracker",
            return_value=mock_tracker,
        ),
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ),
    ):
        # Import RequestOrchestrator AFTER patches are applied to ensure proper patching
        from src.api.orchestrator.request_orchestrator import RequestOrchestrator

        orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        with pytest.raises(HTTPException) as exc_info:
            await orchestrator.prepare_request_context(
                request=request,
                http_request=mock_http_request,
                client_api_key=None,
            )

        assert exc_info.value.status_code == 499
        assert "disconnected" in exc_info.value.detail.lower()
        mock_tracker.end_request.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_applies_middleware_preprocessing() -> None:
    """Test that orchestrator applies middleware to requests."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)

    # Mock middleware chain
    mock_middleware_chain = MagicMock()
    mock_processed_context = MagicMock(
        messages=[{"role": "user", "content": "Modified by middleware"}]
    )
    mock_middleware_chain.process_request = AsyncMock(return_value=mock_processed_context)

    # Create mock config with provider_manager and middleware
    mock_provider_config = create_mock_provider_config(name="gemini")
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="gemini-key",
        has_middleware=True,
        middleware_chain=mock_middleware_chain,
        log_request_metrics=False,
    )

    mock_model_manager = create_mock_model_manager(provider="gemini", model="gemini-2.0-flash")

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ),
    ):
        mock_convert.return_value = {
            "model": "gemini-2.0-flash",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "gemini",
        }

        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        # Verify middleware was called
        mock_middleware_chain.process_request.assert_called_once()
        # Verify messages were modified by middleware
        assert ctx.openai_messages == [{"role": "user", "content": "Modified by middleware"}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_no_middleware_when_not_configured() -> None:
    """Test that orchestrator skips middleware when not configured."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)

    # Create mock config with provider_manager (no middleware)
    mock_provider_config = create_mock_provider_config()
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="sk-prov-key",
        has_middleware=False,
        log_request_metrics=False,
    )

    mock_model_manager = create_mock_model_manager()

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 100, 0),
        ),
    ):
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        # Should not raise any errors
        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        assert ctx.request_id is not None


@pytest.mark.unit
def test_orchestrator_initialization() -> None:
    """Test RequestOrchestrator initialization."""

    mock_model_manager = create_mock_model_manager()
    # Default: metrics enabled
    orchestrator = RequestOrchestrator(
        config=MagicMock(log_request_metrics=True), model_manager=mock_model_manager
    )
    assert orchestrator.config.log_request_metrics is True
    assert orchestrator.log_request_metrics is True

    # Metrics disabled
    orchestrator_no_metrics = RequestOrchestrator(
        config=MagicMock(log_request_metrics=False), model_manager=mock_model_manager
    )
    assert orchestrator_no_metrics.config.log_request_metrics is False
    assert orchestrator_no_metrics.log_request_metrics is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orchestrator_context_contains_all_required_fields() -> None:
    """Test that prepared context contains all expected fields."""
    request = ClaudeMessagesRequest(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello"}],
    )

    mock_http_request = MagicMock()
    mock_http_request.is_disconnected = AsyncMock(return_value=False)

    start = time.time()

    # Create mock config with provider_manager
    mock_provider_config = create_mock_provider_config()
    mock_config = create_mock_config(
        provider_config=mock_provider_config,
        client=MagicMock(),
        api_key="sk-test-key",
        has_middleware=False,
        log_request_metrics=False,
    )

    mock_model_manager = create_mock_model_manager()

    orchestrator = RequestOrchestrator(config=mock_config, model_manager=mock_model_manager)

    with (
        patch("src.api.orchestrator.request_orchestrator.convert_claude_to_openai") as mock_convert,
        patch(
            "src.api.orchestrator.request_orchestrator.populate_request_metrics",
            return_value=(1, 150, 0),
        ),
    ):
        mock_convert.return_value = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "_provider": "openai",
        }

        ctx = await orchestrator.prepare_request_context(
            request=request,
            http_request=mock_http_request,
            client_api_key=None,
        )

        # Verify all required fields are set
        assert ctx.request == request
        assert ctx.openai_request is not None
        assert ctx.request_id is not None
        assert ctx.http_request == mock_http_request
        assert ctx.provider_name == "openai"
        assert ctx.resolved_model == "gpt-4o"
        assert ctx.provider_config == mock_provider_config
        assert ctx.client_api_key is None
        assert ctx.provider_api_key == "sk-test-key"
        assert ctx.openai_client is not None
        assert ctx.metrics is None  # Metrics disabled
        assert ctx.tracker is None
        assert ctx.config is not None
        assert ctx.start_time >= start
        assert ctx.tool_use_count == 0
        assert ctx.tool_result_count == 0
        assert ctx.request_size == 150
        assert ctx.message_count == 1
