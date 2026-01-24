"""Playwright fixtures for E2E UI tests.

This module provides browser automation fixtures for testing the dashboard UI.
Tests use async Playwright API for optimal performance with Dash's async updates.
"""

import pytest


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


@pytest.fixture
async def dashboard_page(page, base_url, page_wait_timeout):
    """Navigate to dashboard models page with configured timeout.

    This fixture pre-navigates to the models page and sets default timeouts.
    """
    await page.goto(f"{base_url}/dashboard/models", wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=page_wait_timeout)
    return page
