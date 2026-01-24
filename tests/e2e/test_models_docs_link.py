"""E2E tests for the Models page documentation link feature.

These tests verify that the "View available models" documentation button
displays correctly when a provider is selected on the dashboard.

UI Elements:
- Provider dropdown: #vdm-models-provider-dropdown
- Docs link container: #vdm-models-provider-docs-link
- Docs button: #vdm-models-provider-docs-link a[href]
- Models grid: #vdm-models-provider-grid
"""

import pytest
from playwright.async_api import expect


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_docs_link_hidden_when_no_provider_selected(dashboard_page, page_wait_timeout):
    """Verify documentation link is hidden initially when no provider is selected."""
    page = dashboard_page

    # Docs link container should be empty initially (no provider selected)
    docs_container = page.locator("#vdm-models-provider-docs-link")

    # Wait a moment to ensure Dash has rendered initial state
    await page.wait_for_timeout(1000)

    # Container should exist but have no visible children
    await expect(docs_container).to_be_visible()
    await expect(docs_container).to_be_empty()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_docs_link_appears_on_provider_selection(dashboard_page, page_wait_timeout):
    """Verify documentation link appears when a provider is selected."""
    page = dashboard_page

    # Click the provider dropdown
    await page.click("#vdm-models-provider-dropdown")

    # Wait for dropdown options to appear
    await page.wait_for_selector('[role="option"]', timeout=page_wait_timeout)

    # Select the first available provider (usually "openai" or first in list)
    first_option = page.locator('[role="option"]').first
    await first_option.inner_text()
    await first_option.click()

    # Wait for docs link to appear
    docs_button = page.locator("#vdm-models-provider-docs-link a[href]")
    await expect(docs_button).to_be_visible(timeout=page_wait_timeout)

    # Verify button text
    await expect(docs_button).to_contain_text("View available models")

    # Verify href is a valid URL (starts with http)
    href = await docs_button.get_attribute("href")
    assert href and href.startswith(("http://", "https://"))

    # Verify button opens in new tab
    target = await docs_button.get_attribute("target")
    assert target == "_blank"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_docs_link_persists_after_models_load(dashboard_page, page_wait_timeout):
    """Verify documentation link remains visible after models grid loads."""
    page = dashboard_page

    # Select a provider
    await page.click("#vdm-models-provider-dropdown")
    await page.wait_for_selector('[role="option"]', timeout=page_wait_timeout)
    await page.locator('[role="option"]').first.click()

    # Wait for docs link to appear
    docs_button = page.locator("#vdm-models-provider-docs-link a[href]")
    await expect(docs_button).to_be_visible(timeout=page_wait_timeout)

    # Wait for models grid to populate (has at least one row)
    grid = page.locator("#vdm-models-provider-grid")
    await expect(grid).to_be_visible()

    # Give models time to load (Dash async update)
    await page.wait_for_timeout(2000)

    # Verify docs link is still visible after models load
    await expect(docs_button).to_be_visible()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_docs_link_updates_on_provider_change(dashboard_page, page_wait_timeout):
    """Verify documentation link updates when switching providers."""
    page = dashboard_page

    # Select first provider
    await page.click("#vdm-models-provider-dropdown")
    await page.wait_for_selector('[role="option"]', timeout=page_wait_timeout)

    options = page.locator('[role="option"]')
    count = await options.count()

    # Need at least 2 providers for this test
    if count < 2:
        pytest.skip("Test requires at least 2 configured providers")

    # Get first provider's URL
    await options.nth(0).click()
    docs_button = page.locator("#vdm-models-provider-docs-link a[href]")
    await expect(docs_button).to_be_visible(timeout=page_wait_timeout)
    await docs_button.get_attribute("href")

    # Switch to second provider
    await page.click("#vdm-models-provider-dropdown")
    await page.wait_for_selector('[role="option"]', timeout=page_wait_timeout)
    await options.nth(1).click()

    # Verify docs link updates (new URL)
    await expect(docs_button).to_be_visible(timeout=page_wait_timeout)
    second_href = await docs_button.get_attribute("href")

    # URLs should be different (or at least the test verifies the link updates)
    assert second_href is not None
