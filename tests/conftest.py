"""Shared pytest configuration and fixtures for Vandamme Proxy tests."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import HTTP mocking fixtures from fixtures module
pytest_plugins = ["tests.fixtures.mock_http"]

# Import test configuration constants


@pytest.fixture
def mock_openai_api_key():
    """Mock OpenAI API key for testing."""
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    yield
    os.environ.pop("OPENAI_API_KEY", None)


@pytest.fixture
def mock_anthropic_api_key():
    """Mock Anthropic API key for testing."""
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
    yield
    os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture
def mock_config():
    """Mock configuration with test values."""
    config = MagicMock()
    config.provider_manager = MagicMock()
    config.proxy_api_key = None
    config.default_provider = "openai"
    config.openai_api_key = "test-key"
    config.openai_base_url = "https://api.openai.com/v1"
    config.log_level = "DEBUG"
    config.max_tokens_limit = 4096
    config.min_tokens_limit = 100
    config.request_timeout = 90
    config.max_retries = 2
    return config


@pytest.fixture
def mock_provider_config():
    """Mock provider configuration."""
    provider_config = MagicMock()
    provider_config.name = "test-provider"
    provider_config.api_key = "test-api-key"
    provider_config.base_url = "https://api.test.com/v1"
    provider_config.api_format = "openai"
    provider_config.api_version = None
    return provider_config


@pytest.fixture
def mock_http_request_with_app_state():
    """Create a mock HTTP request with properly configured app.state.request_tracker.

    This fixture provides a mock request object that has all required
    app.state attributes including request_tracker for metrics tracking.
    Use this in tests that need to pass a mock HTTP request to RequestOrchestrator
    or other components that access request.app.state.
    """
    from src.core.metrics import create_request_tracker

    mock_request = MagicMock()
    mock_request.app = MagicMock()
    mock_request.app.state.request_tracker = create_request_tracker()
    mock_request.is_disconnected = AsyncMock(return_value=False)
    return mock_request


@pytest.fixture(scope="session")
def integration_test_port():
    """Port for integration tests (matching development server)."""
    return int(os.environ.get("VDM_TEST_PORT", "8082"))


@pytest.fixture(scope="session")
def base_url(integration_test_port):
    """Base URL for integration tests."""
    return f"http://localhost:{integration_test_port}"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: No external dependencies, all HTTP mocked")
    config.addinivalue_line("markers", "integration: Local server only, no external APIs")
    config.addinivalue_line("markers", "external: Requires real external API calls and API keys")
    config.addinivalue_line(
        "markers",
        "on_demand: Expensive external test run selectively via make test-on-demand",
    )
    # Legacy support for old e2e marker (will be deprecated)
    config.addinivalue_line(
        "markers",
        "e2e: DEPRECATED - Use 'external' marker instead. Requires real external API calls.",
    )


def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        path = str(item.fspath)

        # Add unit marker to tests in unit/ and middleware/ directories
        if "tests/unit/" in path or "tests/middleware/" in path:
            item.add_marker(pytest.mark.unit)

        # Add on_demand marker to tests in external/on_demand/ directory
        # (also applies external marker since on_demand tests are external)
        elif "tests/external/on_demand/" in path:
            item.add_marker(pytest.mark.on_demand)
            item.add_marker(pytest.mark.external)

        # Add external marker to tests in external/ directory
        elif "tests/external/" in path:
            item.add_marker(pytest.mark.external)

        # Add e2e marker to tests in e2e/ directory (Playwright UI tests)
        elif "tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)

        # Add integration marker to tests in integration/ directory
        elif "tests/integration/" in path:
            item.add_marker(pytest.mark.integration)

        # Legacy handling for tests in root tests/ directory
        elif "tests/" in path:
            # Assume they're unit tests if they use TestClient
            if "TestClient" in item.function.__code__.co_names:
                item.add_marker(pytest.mark.unit)
            # Otherwise mark as integration
            else:
                item.add_marker(pytest.mark.integration)

        # Convert legacy e2e marker to external for backward compatibility
        if item.get_closest_marker("e2e"):
            item.add_marker(pytest.mark.external)


@pytest.fixture(scope="function", autouse=True)
def setup_test_environment_for_unit_tests():
    """Setup test environment for unit tests with minimal provider configuration.

    This fixture runs before each test to ensure a clean environment.
    Unit tests should only need minimal provider setup since all HTTP calls are mocked.

    Strategy:
    1. Set minimal test environment variables
    2. Reset the global config singleton
    3. Clear module cache for affected modules
    4. Restore environment after test completes
    """
    import os

    # Store original environment
    original_env = os.environ.copy()

    # Store original sys.modules state for cleanup
    original_modules = set(sys.modules.keys())

    try:
        # Clear any existing test aliases (both old and new patterns)
        for key in list(os.environ.keys()):
            if "_ALIAS_" in key:
                os.environ.pop(key, None)

        # Set minimal test environment from centralized config
        from tests.config import DEFAULT_TEST_CONFIG, TEST_API_KEYS, TEST_ENDPOINTS

        test_env = {
            # Dummy provider keys for unit tests.
            # These are NOT used to make real network calls (RESPX intercepts HTTP);
            # they exist solely so provider configuration loads and request routing
            # code paths can be exercised offline.
            "OPENAI_API_KEY": TEST_API_KEYS["OPENAI"],
            "ANTHROPIC_API_KEY": TEST_API_KEYS["ANTHROPIC"],
            "ANTHROPIC_BASE_URL": TEST_ENDPOINTS["ANTHROPIC"],
            "ANTHROPIC_API_FORMAT": "anthropic",
            "POE_API_KEY": TEST_API_KEYS["POE"],
            "GLM_API_KEY": TEST_API_KEYS["GLM"],
            "OPENROUTER_API_KEY": TEST_API_KEYS["OPENROUTER"],
            "KIMI_API_KEY": "test-kimi-key",
            # Additional providers needed for profile validation in defaults.toml
            # Note: 'top' is a profile name (#top), not a provider - no TOP_API_KEY needed
            "ZAI_API_KEY": "test-zai-key",
            "AGENTROUTER_API_KEY": "test-agentrouter-key",
            "VDM_DEFAULT_PROVIDER": DEFAULT_TEST_CONFIG["DEFAULT_PROVIDER"],
            "LOG_LEVEL": DEFAULT_TEST_CONFIG["LOG_LEVEL"],
            "LOG_REQUEST_METRICS": "true",
            # Ensure top-models endpoints work deterministically in unit tests.
            "TOP_MODELS_SOURCE": "manual_rankings",
            # Set a default rankings file to avoid Path(".") issues when None
            "TOP_MODELS_RANKINGS_FILE": "",
        }

        os.environ.update(test_env)

        # Clear module cache for modules that need fresh import
        modules_to_clear = [
            "src.core.config",
            "src.core.dependencies",
            "src.core.provider_manager",
            "src.core.provider_config",
            "src.core.provider.client_factory",  # Needed for isinstance tests after module reload
            "src.core.client",
            "src.core.anthropic_client",
            "src.core.alias_manager",
            "src.core.alias_config",
            "src.core.model_manager",
            "src.top_models.service",  # Has module-level config import
            "src.api.services.key_rotation",  # Has module-level config import
            "src.api.services.provider_context",  # Has module-level config import
            # NOTE: request_orchestrator removed from clearing to fix mock issues
            # "src.api.orchestrator.request_orchestrator",
            "src.api.endpoints",
            "src.main",
        ]

        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Reset the AliasConfigLoader cache for test isolation
        from src.core.alias_config import AliasConfigLoader

        AliasConfigLoader.reset_cache()

        # Reset process-global API key rotation state for test isolation
        # This ensures multi-API-key tests start with clean rotation indices
        # Note: Since Config is no longer a singleton, this only affects
        # the module-level state if any Config instances were created
        import src.core.config

        if hasattr(src.core.config, "provider_manager"):
            if hasattr(src.core.config.provider_manager, "_api_key_indices"):
                src.core.config.provider_manager._api_key_indices.clear()
            if hasattr(src.core.config.provider_manager, "_api_key_locks"):
                src.core.config.provider_manager._api_key_locks.clear()
            # Clear cached HTTP clients to prevent SDK client reuse with stale keys
            if hasattr(src.core.config.provider_manager, "_clients"):
                src.core.config.provider_manager._clients.clear()

        # Force reload of modules that import config at module level
        # This ensures they get the new config instance after reset
        modules_to_reload = [
            "src.core.config",  # Must be deleted first so import reloads it
            "src.top_models.service",  # Has module-level config import that gets stale
            "src.api.endpoints",
            "src.main",
        ]

        for module_name in modules_to_reload:
            if module_name in sys.modules:
                del sys.modules[module_name]

        # Import app modules after config reset to ensure they use the fresh config
        import src.main  # noqa: F401

        yield

    finally:
        # Restore original environment completely
        os.environ.clear()
        os.environ.update(original_env)

        # Clear any modules imported during test
        current_modules = set(sys.modules.keys())
        test_modules = current_modules - original_modules
        for module_name in test_modules:
            if module_name.startswith("src.") or module_name.startswith("tests."):
                sys.modules.pop(module_name, None)


# =============================================================================
# Isolation Guards - Prevent tests from crossing category boundaries
# =============================================================================


def _guard_unit_test_network(request: pytest.FixtureRequest) -> None:
    """Guard unit tests to ensure no real HTTP calls are made.

    Unit tests that use HTTP clients must use RESPX mocking.
    RESPX's assert_all_mocked=True will catch any unmocked calls.

    This guard only applies to tests that actually use HTTP-related fixtures.

    Args:
        request: pytest request object

    Raises:
        pytest.fail.Exception: If test uses HTTP clients without proper mocking
    """
    # Check if test is using HTTP-related fixtures
    fixture_names = request.fixturenames

    # pytest's built-in "request" fixture is for test introspection, not HTTP
    # We need to exclude it from our HTTP fixture detection
    http_client_fixtures = {
        "client",
        "http_client",
        "async_client",
        "httpx_client",
        "test_client",
        "ac_client",  # AsyncClient variants
    }

    # Only check for HTTP client fixtures (not pytest's "request" fixture)
    uses_http_client = any(
        fixture in http_client_fixtures or "client" in fixture.lower()
        for fixture in fixture_names
        if fixture != "request"  # Exclude pytest's built-in request fixture
    )

    # Only enforce mocking if the test actually uses HTTP client fixtures
    if not uses_http_client:
        return

    # Check if test has RESPX mocking
    has_resp = any(
        "mock_openai_api" in name or "mock_anthropic_api" in name for name in fixture_names
    )

    if not has_resp:
        # Check if test has a direct marker that might indicate it's intentional
        # (e.g., testing error handling without mocks)
        node = request.node
        for marker in node.iter_markers():
            if marker.name == "allow_unmocked":
                return  # Test explicitly opts out of mocking

        pytest.fail(
            f"Unit test '{request.node.name}' uses HTTP client fixtures without mocking. "
            f"Add 'mock_openai_api' or 'mock_anthropic_api' fixture, or mark with "
            f"@pytest.mark.allow_unmocked if this is intentional."
        )


def _guard_integration_test_network(request: pytest.FixtureRequest) -> None:
    """Guard integration tests to ensure only localhost HTTP calls are made.

    Integration tests may make HTTP calls, but only to the local server.
    This prevents accidental external API calls.

    Args:
        request: pytest request object

    Raises:
        pytest.fail.Exception: If test configuration suggests external calls
    """
    # Check if test is using external API fixtures
    fixture_names = request.fixturenames
    has_external_fixtures = any(
        "external_api_keys" in name or "require_api_keys" in name for name in fixture_names
    )

    if has_external_fixtures:
        pytest.fail(
            f"Integration test '{request.node.name}' uses external test fixtures. "
            f"Move this test to tests/external/ directory."
        )

    # Check if test requires external API keys via marker
    node = request.node
    for marker in node.iter_markers():
        if marker.name == "requires_api_keys":
            pytest.fail(
                f"Integration test '{request.node.name}' requires external API keys. "
                f"Move this test to tests/external/ directory and mark with "
                f"@pytest.mark.external instead."
            )


def _guard_external_test_config(request: pytest.FixtureRequest) -> None:
    """Guard external tests to ensure proper opt-in and API keys.

    Args:
        request: pytest request object

    Raises:
        pytest.skip.Exception: If ALLOW_EXTERNAL_TESTS=1 is not set
    """
    # Import here to avoid circular import
    import os

    opt_in = os.environ.get("ALLOW_EXTERNAL_TESTS", "").lower()
    if opt_in not in ("1", "true", "yes"):
        pytest.skip(
            f"External test '{request.node.name}' requires ALLOW_EXTERNAL_TESTS=1. "
            f"Run: ALLOW_EXTERNAL_TESTS=1 pytest -m external"
        )


@pytest.fixture(scope="function", autouse=True)
def _enforce_isolation_guards(request: pytest.FixtureRequest) -> None:
    """Prevent tests from crossing category boundaries.

    This autouse fixture applies guards based on the test's markers:
    - Unit tests: Must use HTTP mocking (RESPX)
    - Integration tests: Cannot use external API fixtures
    - External tests: Require ALLOW_EXTERNAL_TESTS=1
    - E2E tests (UI/browser): No guards, tests against local dashboard

    Args:
        request: pytest request object
    """
    markers = {m.name for m in request.node.iter_markers()}

    # Skip guards for E2E tests (Playwright UI tests against local dashboard)
    if "e2e" in markers:
        yield
        return

    if "unit" in markers:
        _guard_unit_test_network(request)
    if "integration" in markers:
        _guard_integration_test_network(request)
    if "external" in markers:
        _guard_external_test_config(request)

    yield
