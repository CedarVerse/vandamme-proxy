"""Playwright fixtures for E2E UI tests.

This module provides browser automation fixtures for testing the dashboard UI.
Tests use async Playwright API for optimal performance with Dash's async updates.
"""

import httpx
import pytest
import yaml


@pytest.fixture
def httpx_client():
    """Synchronous HTTP client for E2E test setup.

    Used for fetching health endpoint and other test setup tasks.
    """
    return httpx.Client()


@pytest.fixture
def health_data(base_url, httpx_client):
    """Fetch health endpoint data for E2E test setup.

    Returns parsed YAML health data including provider configurations.

    Fails with clear error if health endpoint is unreachable.
    """
    response = httpx_client.get(f"{base_url}/health")
    response.raise_for_status()

    # Parse YAML response
    return yaml.safe_load(response.text)


@pytest.fixture
def provider_with_models_url(health_data):
    """Get first provider name that has models_url configured.

    This fixture ensures the documentation link feature can be tested.
    It FAILS with a clear error if no provider has models_url configured,
    because the feature requires at least one provider with documentation.

    Error message includes instructions for fixing the test environment.
    """
    providers = health_data.get("providers", {})
    for name, config in providers.items():
        if config.get("models_url"):
            return name

    pytest.fail(
        "E2E test requires at least one provider with models_url configured. "
        "Either configure a provider with models-url in vandamme-config.toml, "
        "or set a {PROVIDER}_MODELS_URL environment variable. "
        "See src/config/defaults.toml for examples."
    )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for E2E tests.

    - Ignore HTTPS errors for local development
    - Set viewport size for consistent testing
    - Record video on failure for debugging
    """
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for E2E tests.

    Tests expect the server to be running at this URL.
    Use `make test-ui` which ensures the server is running.
    """
    return "http://localhost:8082"


@pytest.fixture
def page_wait_timeout() -> int:
    """Default timeout for Playwright wait operations.

    Dash applications update asynchronously, so we use longer timeouts
    than typical web apps to account for server-side rendering and callbacks.
    """
    return 10000  # 10 seconds


@pytest.mark.asyncio(loop_scope="session")
@pytest.fixture
async def dashboard_page(page, base_url, page_wait_timeout):
    """Navigate to dashboard models page with configured timeout.

    This fixture pre-navigates to the models page and sets default timeouts.
    """
    await page.goto(f"{base_url}/dashboard/models", wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=page_wait_timeout)
    return page
