# Three-Tier Test Categorization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement strictly enforced boundaries between three test categories: unit (no external deps), integration (local server only), and external (real API calls).

**Architecture:** Replace `@pytest.mark.e2e` with `@pytest.mark.external`, create `tests/external/` directory, add isolation guards to prevent category boundary violations, require explicit opt-in for external tests via `ALLOW_EXTERNAL_TESTS=1` environment variable.

**Tech Stack:** pytest, RESPX (HTTP mocking), httpx, environment variable configuration, Makefile targets

---

## Overview

This plan enforces strict separation between test categories:

| Category | Location | External Dependencies | API Calls | Opt-in Required |
|----------|----------|----------------------|-----------|-----------------|
| **unit** | `tests/unit/` | None (all mocked via RESPX) | None | No |
| **integration** | `tests/integration/` | Running local server | Only localhost | No |
| **external** | `tests/external/` | Real external APIs | Real HTTP calls | Yes (`ALLOW_EXTERNAL_TESTS=1`) |

**Key Changes:**
- Marker rename: `@pytest.mark.e2e` → `@pytest.mark.external`
- New directory: `tests/external/` for tests requiring real APIs
- Isolation guards: Prevent tests from crossing category boundaries
- External test opt-in: `ALLOW_EXTERNAL_TESTS=1` required to run external tests
- Fail-fast behavior: Missing API keys fail (not skip) by default

---

## Task 1: Create `tests/external/` Directory Structure

**Files:**
- Create: `tests/external/__init__.py`
- Create: `tests/external/conftest.py`

---

### Step 1: Create `tests/external/__init__.py`

**File:** `tests/external/__init__.py`

```python
"""External tests for Vandamme Proxy.

External tests make real HTTP calls to external APIs and require:
1. A running proxy server
2. Valid API keys for the provider being tested
3. ALLOW_EXTERNAL_TESTS=1 environment variable

These tests are NOT run by default to prevent:
- Accidental API charges
- Flaky tests due to network issues
- Slow test runs during development
"""

__all__ = []
```

**Step 2: Create the file**

```bash
cat > tests/external/__init__.py << 'EOF'
"""External tests for Vandamme Proxy.

External tests make real HTTP calls to external APIs and require:
1. A running proxy server
2. Valid API keys for the provider being tested
3. ALLOW_EXTERNAL_TESTS=1 environment variable

These tests are NOT run by default to prevent:
- Accidental API charges
- Flaky tests due to network issues
- Slow test runs during development
"""

__all__ = []
EOF
```

**Step 3: Create `tests/external/conftest.py`**

**File:** `tests/external/conftest.py`

```python
"""Configuration for external tests requiring real API calls.

External tests:
- Make real HTTP calls to external APIs
- Require valid API keys
- Require ALLOW_EXTERNAL_TESTS=1 environment variable
- Fail fast if API keys are missing (configurable via EXTERNAL_TESTS_SKIP_MISSING)
"""

import os
from typing import Any

import pytest


class ExternalTestConfig:
    """Manages configuration for external tests.

    Provides methods to check for required API keys and validate
    external test opt-in status.
    """

    # Provider API key environment variable names
    PROVIDER_API_KEYS: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_API_KEY",
        "poe": "POE_API_KEY",
        "glm": "GLM_API_KEY",
        "bedrock": "BEDROCK_API_KEY",
        "vertex": "VERTEX_API_KEY",
        "zai": "ZAI_API_KEY",
        "zaio": "ZAIO_API_KEY",
        "custom": "CUSTOM_API_KEY",
    }

    @classmethod
    def has_api_key(cls, provider: str) -> bool:
        """Check if API key exists for the given provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            True if API key is set and non-empty
        """
        env_var = cls.PROVIDER_API_KEYS.get(provider)
        if not env_var:
            return False
        api_key = os.environ.get(env_var, "")
        return bool(api_key and api_key.strip())

    @classmethod
    def get_api_key(cls, provider: str) -> str | None:
        """Get the API key for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            The API key value or None if not set
        """
        env_var = cls.PROVIDER_API_KEYS.get(provider)
        if not env_var:
            return None
        api_key = os.environ.get(env_var, "")
        return api_key.strip() if api_key.strip() else None

    @classmethod
    def is_external_test_opt_in_enabled(cls) -> bool:
        """Check if external test opt-in is enabled.

        Returns:
            True if ALLOW_EXTERNAL_TESTS is set to "1" or "true"
        """
        opt_in = os.environ.get("ALLOW_EXTERNAL_TESTS", "").lower()
        return opt_in in ("1", "true", "yes")

    @classmethod
    def should_skip_missing_keys(cls) -> bool:
        """Check if tests should skip when API keys are missing.

        Returns:
            True if EXTERNAL_TESTS_SKIP_MISSING is set to "1" or "true"
        """
        skip_missing = os.environ.get("EXTERNAL_TESTS_SKIP_MISSING", "").lower()
        return skip_missing in ("1", "true", "yes")

    @classmethod
    def verify_external_test_opt_in(cls) -> None:
        """Verify that external test opt-in is enabled.

        Raises:
            pytest.skip.Exception: If ALLOW_EXTERNAL_TESTS is not set
        """
        if not cls.is_external_test_opt_in_enabled():
            pytest.skip(
                "External tests require ALLOW_EXTERNAL_TESTS=1. "
                "Run: ALLOW_EXTERNAL_TESTS=1 pytest -m external"
            )

    @classmethod
    def verify_provider_api_key(cls, provider: str) -> None:
        """Verify that API key exists for the given provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Raises:
            pytest.skip.Exception: If EXTERNAL_TESTS_SKIP_MISSING is set
            pytest.fail.Exception: If API key is missing and skip is disabled
        """
        if not cls.has_api_key(provider):
            env_var = cls.PROVIDER_API_KEYS.get(provider, f"{provider.upper()}_API_KEY")
            if cls.should_skip_missing_keys():
                pytest.skip(f"{env_var} not set")
            else:
                pytest.fail(
                    f"{env_var} is required for this test. "
                    f"Set the API key or run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )


@pytest.fixture(scope="session")
def external_test_config():
    """Provide external test configuration."""
    return ExternalTestConfig


@pytest.fixture(autouse=True)
def verify_external_test_opt_in():
    """Verify external test opt-in before running any external test.

    This fixture automatically applies to all tests in the external/ directory.
    Tests will be skipped unless ALLOW_EXTERNAL_TESTS=1 is set.
    """
    # Only apply to tests marked as external
    # (The marker is auto-applied to tests in tests/external/ directory)
    yield


@pytest.fixture
def require_api_keys(external_test_config: type[ExternalTestConfig]):
    """Factory fixture that creates API key requirement fixtures.

    Usage in tests:
        @pytest.mark.requires_api_keys("openai", "anthropic")
        def test_something(require_api_keys):
            # This test will fail if OPENAI_API_KEY or ANTHROPIC_API_KEY are missing

    Returns:
        A function that takes provider names and verifies their API keys
    """
    def _require_keys(*providers: str) -> None:
        """Verify API keys exist for the given providers.

        Args:
            *providers: One or more provider names (e.g., "openai", "anthropic")

        Raises:
            pytest.skip.Exception: If EXTERNAL_TESTS_SKIP_MISSING is set
            pytest.fail.Exception: If any API key is missing and skip is disabled
        """
        missing_keys = []
        for provider in providers:
            if not external_test_config.has_api_key(provider):
                env_var = external_test_config.PROVIDER_API_KEYS.get(
                    provider, f"{provider.upper()}_API_KEY"
                )
                missing_keys.append(env_var)

        if missing_keys:
            if external_test_config.should_skip_missing_keys():
                pytest.skip(
                    f"Missing required API keys: {', '.join(missing_keys)}. "
                    f"Run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )
            else:
                pytest.fail(
                    f"Missing required API keys: {', '.join(missing_keys)}. "
                    f"Set the keys or run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )

    return _require_keys


@pytest.fixture
def external_api_keys(external_test_config: type[ExternalTestConfig]):
    """Provide access to available external API keys.

    Returns a dict mapping provider names to their API key values
    for providers that have keys configured.

    Usage:
        def test_something(external_api_keys):
            openai_key = external_api_keys.get("openai")
            if openai_key:
                # Use the key
    """
    available_keys = {}
    for provider, env_var in external_test_config.PROVIDER_API_KEYS.items():
        key = external_test_config.get_api_key(provider)
        if key:
            available_keys[provider] = key
    return available_keys


def pytest_configure(config):
    """Register custom markers for external tests."""
    config.addinivalue_line(
        "markers",
        "requires_api_keys(provider, ...): Test requires API keys for specified providers",
    )
```

**Step 4: Create the file**

```bash
cat > tests/external/conftest.py << 'EOF'
# Paste the content from Step 3
EOF
```

**Step 5: Verify files created**

```bash
ls -la tests/external/
```

Expected: Both `__init__.py` and `conftest.py` exist

**Step 6: Commit**

```bash
git add tests/external/
git commit -m "feat(tests): create external test directory structure

- Add tests/external/__init__.py with module documentation
- Add tests/external/conftest.py with ExternalTestConfig class
- Implement ALLOW_EXTERNAL_TESTS=1 opt-in verification
- Implement EXTERNAL_TESTS_SKIP_MISSING for lenient mode
- Add requires_api_keys marker for provider-specific tests

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Update Root `conftest.py` with New Markers and Guards

**Files:**
- Modify: `tests/conftest.py:90-120` (marker definitions and auto-marking)

---

### Step 1: Update marker definitions in `pytest_configure`

**File:** `tests/conftest.py` (lines 90-98)

**Before:**
```python
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests (fast, no external deps)")
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires services)"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests (requires valid API keys)"
    )
```

**After:**
```python
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: No external dependencies, all HTTP mocked")
    config.addinivalue_line("markers", "integration: Local server only, no external APIs")
    config.addinivalue_line(
        "markers", "external: Requires real external API calls and API keys"
    )
    # Legacy support for old e2e marker (will be deprecated)
    config.addinivalue_line(
        "markers",
        "e2e: DEPRECATED - Use 'external' marker instead. Requires real external API calls.",
    )
```

---

### Step 2: Update auto-marking logic for `external/` directory

**File:** `tests/conftest.py` (lines 101-120)

**Before:**
```python
def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        # Add unit marker to tests in unit/ and middleware/ directories
        if "tests/unit/" in str(item.fspath) or "tests/middleware/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add integration marker to tests in integration/ directory
        elif "tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Legacy handling for tests in root tests/ directory
        elif "tests/" in str(item.fspath):
            # Assume they're unit tests if they use TestClient
            if "TestClient" in item.function.__code__.co_names:
                item.add_marker(pytest.mark.unit)
            # Otherwise mark as integration
            else:
                item.add_marker(pytest.mark.integration)
```

**After:**
```python
def pytest_collection_modifyitems(config, items):
    """Add markers to tests based on their location."""
    for item in items:
        path = str(item.fspath)

        # Add unit marker to tests in unit/ and middleware/ directories
        if "tests/unit/" in path or "tests/middleware/" in path:
            item.add_marker(pytest.mark.unit)

        # Add external marker to tests in external/ directory
        elif "tests/external/" in path:
            item.add_marker(pytest.mark.external)
            # Also verify opt-in for external tests
            config.pluginmanager.hook.pytest_collection_modifyitems(
                session=item.session, config=config, items=[item]
            )

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
```

---

### Step 3: Add isolation guard fixture

**File:** `tests/conftest.py` (add at end of file, after line 248)

**Add:**
```python
# =============================================================================
# Isolation Guards - Prevent tests from crossing category boundaries
# =============================================================================


def _guard_unit_test_network(request: pytest.FixtureRequest) -> None:
    """Guard unit tests to ensure no real HTTP calls are made.

    Unit tests must use RESPX mocking. If a real HTTP call is attempted,
    RESPX's assert_all_mocked=True will catch it.

    Args:
        request: pytest request object

    Raises:
        pytest.fail.Exception: If test is not using proper HTTP mocking
    """
    # Check if test is using RESPX mocking
    fixture_names = request.fixturenames
    has_resp = any("mock_openai_api" in name or "mock_anthropic_api" in name
                   for name in fixture_names)

    if not has_resp:
        # Check if test has a direct marker that might indicate it's intentional
        # (e.g., testing error handling without mocks)
        node = request.node
        for marker in node.iter_markers():
            if marker.name == "allow_unmocked":
                return  # Test explicitly opts out of mocking

        pytest.fail(
            f"Unit test '{request.node.name}' must use HTTP mocking fixtures. "
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
        "external_api_keys" in name or "require_api_keys" in name
        for name in fixture_names
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

    Args:
        request: pytest request object
    """
    markers = {m.name for m in request.node.iter_markers()}

    if "unit" in markers:
        _guard_unit_test_network(request)
    if "integration" in markers:
        _guard_integration_test_network(request)
    if "external" in markers:
        _guard_external_test_config(request)

    yield
```

**Step 4: Verify changes**

```bash
grep -A 20 "def pytest_configure" tests/conftest.py
```

Expected: Updated marker definitions with "external" marker

**Step 5: Verify auto-marking includes external directory**

```bash
grep -A 30 "def pytest_collection_modifyitems" tests/conftest.py
```

Expected: Logic to add `external` marker for tests in `tests/external/`

**Step 6: Run unit tests to verify no regression**

```bash
make test-unit
```

Expected: All unit tests pass

**Step 7: Commit**

```bash
git add tests/conftest.py
git commit -m "feat(tests): add external marker and isolation guards

- Rename e2e marker to external (with e2e as deprecated alias)
- Add auto-marking for tests/external/ directory
- Implement isolation guards:
  - Unit tests must use HTTP mocking
  - Integration tests cannot use external fixtures
  - External tests require ALLOW_EXTERNAL_TESTS=1
- Prevent tests from crossing category boundaries

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Migrate ZAI Provider Tests to External

**Files:**
- Create: `tests/external/test_zai_provider.py`
- Modify: `tests/integration/test_api_endpoints.py` (lines 528-550, remove ZAI test)

---

### Step 1: Read the existing ZAI test

**File:** `tests/integration/test_api_endpoints.py` (lines 528-550)

```bash
sed -n '528,550p' tests/integration/test_api_endpoints.py
```

---

### Step 2: Create `tests/external/test_zai_provider.py`

**File:** `tests/external/test_zai_provider.py`

```python
"""External tests for ZAI provider.

These tests make real API calls to ZAI and require:
1. A running proxy server
2. ZAI_API_KEY environment variable
3. ALLOW_EXTERNAL_TESTS=1 environment variable
"""

import os

import httpx
import pytest


# Get test configuration
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.external
@pytest.mark.requires_api_keys("zai")
@pytest.mark.asyncio
async def test_zai_anthropic_passthrough():
    """Test Anthropic API passthrough format with real ZAI API."""
    if not os.getenv("ZAI_API_KEY"):
        pytest.skip("ZAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zai:GLM-4.7",
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "role" in data
        assert data["role"] == "assistant"
```

---

### Step 3: Create the file

```bash
cat > tests/external/test_zai_provider.py << 'EOF'
# Paste the content from Step 2
EOF
```

---

### Step 4: Remove ZAI test from integration file

**File:** `tests/integration/test_api_endpoints.py` (lines 528-550)

**Before:**
```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_anthropic_passthrough():
    """Test Anthropic API passthrough format with real API."""
    if not os.getenv("ZAI_API_KEY"):
        pytest.skip("ZAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zai:GLM-4.7",
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "role" in data
        assert data["role"] == "assistant"
```

**After:**
```python
# ZAI provider tests moved to tests/external/test_zai_provider.py
```

---

### Step 5: Verify the ZAI test file exists

```bash
ls -la tests/external/test_zai_provider.py
```

Expected: File exists

---

### Step 6: Verify integration file no longer has ZAI test

```bash
grep -n "test_anthropic_passthrough" tests/integration/test_api_endpoints.py
```

Expected: Only comment reference, no test function

**Step 7: Commit**

```bash
git add tests/external/test_zai_provider.py tests/integration/test_api_endpoints.py
git commit -m "refactor(tests): migrate ZAI provider tests to external

- Move test_anthropic_passthrough to tests/external/test_zai_provider.py
- Change marker from @pytest.mark.e2e to @pytest.mark.external
- Add @pytest.mark.requires_api_keys(\"zai\") decorator
- Remove test from integration suite

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Migrate ZAIO Provider Tests to External

**Files:**
- Create: `tests/external/test_zaio_provider.py`
- Modify: `tests/integration/test_api_endpoints.py` (lines 217-527, remove ZAIO tests)

---

### Step 1: Read the existing ZAIO tests

**File:** `tests/integration/test_api_endpoints.py` (lines 217-527)

```bash
sed -n '217,527p' tests/integration/test_api_endpoints.py
```

---

### Step 2: Create `tests/external/test_zaio_provider.py`

**File:** `tests/external/test_zaio_provider.py`

```python
"""External tests for ZAIO provider.

These tests make real API calls to ZAIO and require:
1. A running proxy server
2. ZAIO_API_KEY environment variable
3. ALLOW_EXTERNAL_TESTS=1 environment variable
"""

import os

import httpx
import pytest


# Get test configuration
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_basic_chat():
    """Test basic chat completion with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "Say 'Hello world'"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0
        assert "role" in data
        assert data["role"] == "assistant"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_streaming_chat():
    """Test streaming chat completion with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with (
        httpx.AsyncClient(timeout=30.0) as client,
        client.stream(
            "POST",
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.5-Air",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": "Count to 3"}],
                "stream": True,
            },
        ) as response,
    ):
        assert response.status_code == 200

        # Collect streamed events
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(line[6:])  # Remove "data: " prefix

        # Should have at least some events
        assert len(events) > 0

        # Check for event stream format
        assert any("message_start" in event for event in events)
        assert any("content_block_start" in event for event in events)
        assert any("content_block_stop" in event for event in events)
        assert any("message_stop" in event for event in events)


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_function_calling():
    """Test function calling with real ZAIO API."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": "What's 2 + 2? Use the calculator tool.",
                    }
                ],
                "tools": [
                    {
                        "name": "calculator",
                        "description": "Perform basic arithmetic",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression",
                                },
                            },
                            "required": ["expression"],
                        },
                    }
                ],
                "tool_choice": {"type": "auto"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data

        # Should have tool_use in content
        tool_use_found = False
        for content_block in data.get("content", []):
            if content_block.get("type") == "tool_use":
                tool_use_found = True
                assert "id" in content_block
                assert "name" in content_block
                assert content_block["name"] == "calculator"

        assert tool_use_found, "Expected tool_use block in response"


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_with_system_message():
    """Test with system message."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "system": (
                    "You are a helpful assistant that always ends responses with 'over and out'."
                ),
                "messages": [{"role": "user", "content": "Say hello"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0

        # Check that the response follows the system instruction
        content_text = data["content"][0].get("text", "").lower()
        assert "over and out" in content_text


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_multimodal():
    """Test multimodal input (text + image)."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Small 1x1 pixel red PNG
        sample_image = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/"
            "PchI7wAAAABJRU5ErkJggg=="
        )

        response = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What color is this image?"},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": sample_image,
                                },
                            },
                        ],
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_conversation_with_tool_use():
    """Test a complete conversation with tool use and results."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # First message with tool call
        response1 = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": "Calculate 25 * 4"}],
                "tools": [
                    {
                        "name": "calculator",
                        "description": "Perform arithmetic calculations",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to calculate",
                                }
                            },
                            "required": ["expression"],
                        },
                    }
                ],
            },
        )

        assert response1.status_code == 200
        result1 = response1.json()

        # Note: tool calling behavior is provider/model dependent
        tool_use_blocks = [
            block for block in result1.get("content", []) if block.get("type") == "tool_use"
        ]
        if not tool_use_blocks:
            content_text = " ".join(
                block.get("text", "")
                for block in result1.get("content", [])
                if block.get("type") == "text"
            ).lower()
            assert "100" in content_text
            return

        # Simulate tool execution and send result
        tool_block = tool_use_blocks[0]

        response2 = await client.post(
            f"{BASE_URL}/v1/messages",
            json={
                "model": "zaio:GLM-4.7",
                "max_tokens": 50,
                "messages": [
                    {"role": "user", "content": "Calculate 25 * 4"},
                    {"role": "assistant", "content": result1["content"]},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_block["id"],
                                "content": "100",
                            }
                        ],
                    },
                ],
            },
        )

        assert response2.status_code == 200
        result2 = response2.json()
        assert "content" in result2

        # Should acknowledge the calculation result
        content_text = " ".join(
            block.get("text", "")
            for block in result2.get("content", [])
            if block.get("type") == "text"
        ).lower()
        assert "100" in content_text


@pytest.mark.external
@pytest.mark.requires_api_keys("zaio")
@pytest.mark.asyncio
async def test_zaio_token_counting():
    """Test token counting endpoint."""
    if not os.getenv("ZAIO_API_KEY"):
        pytest.skip("ZAIO_API_KEY not set")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/messages/count_tokens",
            json={
                "model": "zaio:GLM-4.7",
                "messages": [
                    {"role": "user", "content": "This is a test message for token counting."}
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "input_tokens" in data
        assert data["input_tokens"] > 0
```

---

### Step 3: Create the file

```bash
cat > tests/external/test_zaio_provider.py << 'EOF'
# Paste the content from Step 2
EOF
```

---

### Step 4: Remove ZAIO tests from integration file

**File:** `tests/integration/test_api_endpoints.py` (lines 217-527)

**Before:**
```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_basic_chat():
    # ... (all ZAIO tests)

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_streaming_chat():
    # ...

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_function_calling():
    # ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_with_system_message():
    # ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_multimodal():
    # ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_conversation_with_tool_use():
    # ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_counting():
    # ...
```

**After:**
```python
# ZAIO provider tests moved to tests/external/test_zaio_provider.py
# - test_basic_chat (was test_basic_chat with @pytest.mark.e2e)
# - test_streaming_chat (was test_streaming_chat with @pytest.mark.e2e)
# - test_function_calling (was test_function_calling with @pytest.mark.e2e)
# - test_zaio_with_system_message (was test_with_system_message)
# - test_zaio_multimodal (was test_multimodal)
# - test_zaio_conversation_with_tool_use (was test_conversation_with_tool_use)
# - test_zaio_token_counting (was test_token_counting)
```

---

### Step 5: Verify files

```bash
ls -la tests/external/test_zaio_provider.py
wc -l tests/external/test_zaio_provider.py
```

Expected: File exists with ~250 lines

---

### Step 6: Verify integration file cleaned up

```bash
grep -c "ZAIO" tests/integration/test_api_endpoints.py
```

Expected: Only comment references remain

**Step 7: Commit**

```bash
git add tests/external/test_zaio_provider.py tests/integration/test_api_endpoints.py
git commit -m "refactor(tests): migrate ZAIO provider tests to external

- Move all ZAIO tests to tests/external/test_zaio_provider.py
- Change markers from @pytest.mark.e2e to @pytest.mark.external
- Add @pytest.mark.requires_api_keys(\"zaio\") decorators
- Rename tests with test_zaio_ prefix for clarity
- Remove tests from integration suite

Tests migrated:
- test_basic_chat → test_zaio_basic_chat
- test_streaming_chat → test_zaio_streaming_chat
- test_function_calling → test_zaio_function_calling
- test_with_system_message → test_zaio_with_system_message
- test_multimodal → test_zaio_multimodal
- test_conversation_with_tool_use → test_zaio_conversation_with_tool_use
- test_token_counting → test_zaio_token_counting

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Update Makefile Targets

**Files:**
- Modify: `Makefile` (lines 268-345, test targets section)

---

### Step 1: Read current test targets

**File:** `Makefile` (lines 268-345)

```bash
sed -n '268,345p' Makefile
```

---

### Step 2: Update `.PHONY` declaration

**File:** `Makefile` (line 15)

**Before:**
```makefile
.PHONY: help dev-env-init dev-deps-sync run dev health clean watch doctor check-install sanitize format lint typecheck security-check validate test test-unit test-integration test-e2e test-all test-quick coverage check check-quick ci build all pre-commit docker-build docker-up docker-down docker-logs docker-restart docker-clean build-cli clean-binaries version version-set version-bump tag-release release-check release-build release-publish release release-full release-patch release-minor release-major info env-template deps-check
```

**After:**
```makefile
.PHONY: help dev-env-init dev-deps-sync run dev health clean watch doctor check-install sanitize format lint typecheck security-check validate test test-unit test-integration test-external test-e2e test-all test-quick coverage check check-quick ci build all pre-commit docker-build docker-up docker-down docker-logs docker-restart docker-clean build-cli clean-binaries version version-set version-bump tag-release release-check release-build release-publish release release-full release-patch release-minor release-major info env-template deps-check .ensure-server-running .ensure-external-opt-in
```

---

### Step 3: Add new test targets

**File:** `Makefile` (insert after line 310, after `test-integration` target)

**Add:**
```makefile
test-external: ## Run external tests (requires API keys and ALLOW_EXTERNAL_TESTS=1)
	@printf "$(BOLD)$(CYAN)Running external tests...$(RESET)\n"
	@printf "$(YELLOW)⚠ These tests make real API calls and will incur costs$(RESET)\n"
	@$(MAKE) -s .ensure-server-running
	@$(MAKE) -s .ensure-external-opt-in
	@printf "$(CYAN)Note: Ensure API keys are set in .env$(RESET)\n"
	$(UV) run $(PYTEST) $(TEST_DIR) -v -m external

test-external-oneshot: ## Run external tests (one-shot mode with opt-in)
	@printf "$(BOLD)$(CYAN)Running external tests (one-shot mode)...$(RESET)\n"
	@printf "$(YELLOW)⚠ These tests make real API calls and will incur costs$(RESET)\n"
	@$(MAKE) -s .ensure-server-running
	ALLOW_EXTERNAL_TESTS=1 $(UV) run $(PYTEST) $(TEST_DIR) -v -m external

test-external-lenient: ## Run external tests (skipping if keys missing)
	@printf "$(BOLD)$(CYAN)Running external tests (lenient mode)...$(RESET)\n"
	@printf "$(YELLOW)⚠ These tests make real API calls and will incur costs$(RESET)\n"
	@printf "$(YELLOW)ℹ️ Tests will skip if their required API keys are missing$(RESET)\n"
	@$(MAKE) -s .ensure-server-running
	ALLOW_EXTERNAL_TESTS=1 EXTERNAL_TESTS_SKIP_MISSING=1 $(UV) run $(PYTEST) $(TEST_DIR) -v -m external
```

---

### Step 4: Update `test-e2e` target (legacy alias)

**File:** `Makefile` (lines 299-309)

**Before:**
```makefile
test-e2e: ## Run end-to-end tests with real APIs (requires server and API keys)
	@printf "$(BOLD)$(CYAN)Running end-to-end tests...$(RESET)\n"
	@printf "$(YELLOW)⚠ These tests make real API calls and will incur costs$(RESET)\n"
	@printf "$(YELLOW)Note: Ensure server is running and API keys are set in .env$(RESET)\n"
	@if curl -s http://localhost:$(PORT)/health > /dev/null 2>&1 || \
	   curl -s http://localhost:18082/health > /dev/null 2>&1; then \
		$(UV) run $(PYTEST) $(TEST_DIR) -v -m e2e; \
	else \
		printf "$(RED)❌ Server not running. Start with 'make dev' first$(RESET)\n"; \
		exit 1; \
	fi
```

**After:**
```makefile
test-e2e: ## DEPRECATED: Use 'test-external' instead. Run external tests with real APIs
	@printf "$(YELLOW)⚠ WARNING: 'test-e2e' is deprecated. Use 'make test-external' instead.$(RESET)\n"
	@$(MAKE) test-external
```

---

### Step 5: Update `test-all` target

**File:** `Makefile` (lines 311-326)

**Before:**
```makefile
test-all: ## Run ALL tests including e2e (requires server and API keys)
	@printf "$(BOLD)$(CYAN)Running ALL tests (unit + integration + e2e)...$(RESET)\n"
	@printf "$(YELLOW)⚠ E2E tests make real API calls and will incur costs$(RESET)\n"
	@# First run unit tests
	@$(UV) run $(PYTEST) $(TEST_DIR) -v -m unit
	@# Then check if server is running for integration and e2e tests
	@if curl -s http://localhost:$(PORT)/health > /dev/null 2>&1 || \
	   curl -s http://localhost:18082/health > /dev/null 2>&1; then \
		printf "$(YELLOW)Server detected, running integration tests...$(RESET)\n"; \
		$(UV) run $(PYTEST) $(TEST_DIR) -v -m "integration and not e2e" || printf "$(YELLOW)⚠ Some integration tests failed$(RESET)\n"; \
		printf "$(YELLOW)Running e2e tests...$(RESET)\n"; \
		$(UV) run $(PYTEST) $(TEST_DIR) -v -m e2e || printf "$(YELLOW)⚠ Some e2e tests failed (check API keys)$(RESET)\n"; \
	else \
		printf "$(RED)❌ Server not running. Start with 'make dev' first$(RESET)\n"; \
		exit 1; \
	fi
```

**After:**
```makefile
test-all: ## Run ALL tests including external (requires server and API keys)
	@printf "$(BOLD)$(CYAN)Running ALL tests (unit + integration + external)...$(RESET)\n"
	@printf "$(YELLOW)⚠ External tests make real API calls and will incur costs$(RESET)\n"
	@# First run unit tests
	@$(UV) run $(PYTEST) $(TEST_DIR) -v -m unit
	@# Then check if server is running for integration tests
	@if curl -s http://localhost:$(PORT)/health > /dev/null 2>&1 || \
	   curl -s http://localhost:18082/health > /dev/null 2>&1; then \
		printf "$(YELLOW)Server detected, running integration tests...$(RESET)\n"; \
		$(UV) run $(PYTEST) $(TEST_DIR) -v -m integration || printf "$(YELLOW)⚠ Some integration tests failed$(RESET)\n"; \
		printf "$(YELLOW)Running external tests...$(RESET)\n"; \
		$(MAKE) test-external-oneshot || printf "$(YELLOW)⚠ Some external tests failed (check API keys)$(RESET)\n"; \
	else \
		printf "$(RED)❌ Server not running. Start with 'make dev' first$(RESET)\n"; \
		exit 1; \
	fi
```

---

### Step 6: Update `test` target behavior (ensure external tests not included)

**File:** `Makefile` (lines 268-282)

**Verify current behavior:**
```bash
grep -A 15 "^test:" Makefile
```

Expected: Current `test` target already excludes e2e, should now also exclude external

---

### Step 7: Add helper targets

**File:** `Makefile` (add after line 345, after `coverage` target)

**Add:**
```makefile
# =============================================================================
# Helper Targets
# =============================================================================

.ensure-server-running:
	@if ! curl -s http://localhost:$(PORT)/health > /dev/null 2>&1 && \
	   ! curl -s http://localhost:18082/health > /dev/null 2>&1; then \
		printf "$(RED)❌ Server not running on port $(PORT) or 18082$(RESET)\n"; \
		printf "$(CYAN)Start server with: make dev$(RESET)\n"; \
		exit 1; \
	fi

.ensure-external-opt-in:
	@if [ -z "$(ALLOW_EXTERNAL_TESTS)" ]; then \
		printf "$(RED)❌ External tests require ALLOW_EXTERNAL_TESTS=1$(RESET)\n"; \
		printf "$(CYAN)Run: ALLOW_EXTERNAL_TESTS=1 make test-external$(RESET)\n"; \
		printf "$(CYAN)Or use one-shot mode: make test-external-oneshot$(RESET)\n"; \
		exit 1; \
	fi
```

---

### Step 8: Update help target

**File:** `Makefile` (line 89-92)

**Before:**
```makefile
	@printf "$(BOLD)Testing:$(RESET)\n"
	@grep -E '^test.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@grep -E '^coverage.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
```

The help target will automatically pick up the new targets due to the grep pattern.

**Step 9: Verify Makefile syntax**

```bash
make help | grep -A 20 "Testing:"
```

Expected: Shows all test targets including `test-external`

**Step 10: Commit**

```bash
git add Makefile
git commit -m "feat(tests): add external test targets to Makefile

- Add test-external target (requires ALLOW_EXTERNAL_TESTS=1)
- Add test-external-oneshot target (auto-enables opt-in)
- Add test-external-lenient target (skips if keys missing)
- Deprecate test-e2e target (redirects to test-external)
- Update test-all to use external marker
- Add .ensure-server-running helper
- Add .ensure-external-opt-in helper

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md` (Testing section)

---

### Step 1: Read current testing section

**File:** `CLAUDE.md` (lines 76-110)

```bash
sed -n '76,110p' CLAUDE.md
```

---

### Step 2: Update testing section

**File:** `CLAUDE.md` (lines 76-110)

**Before:**
```markdown
### Testing

The test suite follows a three-tier pyramid strategy:

1. **Unit Tests** (~90%): Fast, mocked, no external dependencies
2. **Integration Tests** (~10%): Require running server, no API calls
3. **E2E Tests** (<5%): Real API calls for critical validation

```bash
# Run all tests except e2e (default - no API costs)
make test

# Run unit tests only (fastest)
make test-unit

# Run integration tests (requires server, no API calls)
make test-integration

# Run e2e tests with real APIs (requires API keys, incurs costs)
make test-e2e

# Run ALL tests including e2e (full validation)
make test-all

# Quick tests without coverage
make test-quick

# Test configuration and connectivity
vdm test connection
vdm test models
vdm health upstream
vdm config validate
```
```

**After:**
```markdown
### Testing

The test suite follows a strictly enforced three-tier categorization:

| Category | Location | Dependencies | API Calls | Default |
|----------|----------|--------------|-----------|---------|
| **unit** | `tests/unit/` | None (RESPX mocked) | None | Yes |
| **integration** | `tests/integration/` | Running local server | Only localhost | Yes |
| **external** | `tests/external/` | Real external APIs | Real HTTP | No (opt-in) |

```bash
# Run default tests (unit + integration, no API costs)
make test

# Run unit tests only (fast, all mocked)
make test-unit

# Run integration tests (requires server, localhost only)
make test-integration

# Run external tests (requires API keys + opt-in)
ALLOW_EXTERNAL_TESTS=1 make test-external

# External test one-shot mode (auto-enables opt-in)
make test-external-oneshot

# External test lenient mode (skips if keys missing)
ALLOW_EXTERNAL_TESTS=1 EXTERNAL_TESTS_SKIP_MISSING=1 make test-external

# Run ALL tests including external (full validation)
make test-all

# Quick tests without coverage
make test-quick

# Test configuration and connectivity
vdm test connection
vdm test models
vdm health upstream
vdm config validate
```

**External Test Opt-In:**
- `ALLOW_EXTERNAL_TESTS=1` - Required to run external tests (prevents accidental API charges)
- `EXTERNAL_TESTS_SKIP_MISSING=1` - Skip tests when their required API keys are missing

**Deprecated:**
- `make test-e2e` - Use `make test-external` instead
```

---

### Step 3: Update HTTP Mocking section (if it mentions e2e)

**File:** `CLAUDE.md` (lines 120-150)

Search for any remaining references to `e2e` and update to `external`.

**Step 4: Verify changes**

```bash
grep -n "test-e2e\|@pytest.mark.e2e" CLAUDE.md
```

Expected: Only in deprecation notice

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(tests): update documentation for three-tier test categorization

- Update testing section with new category table
- Document ALLOW_EXTERNAL_TESTS=1 opt-in requirement
- Document EXTERNAL_TESTS_SKIP_MISSING lenient mode
- Add test-external, test-external-oneshot, test-external-lenient targets
- Deprecate test-e2e in documentation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Run Verification Tests

**Files:**
- No file modifications

---

### Step 1: Verify unit tests still pass

```bash
make test-unit
```

Expected: All unit tests pass, no network calls

---

### Step 2: Verify integration tests still pass

```bash
# Start server in background if not running
make dev &
SERVER_PID=$!

# Wait for server to start
sleep 5

# Run integration tests
make test-integration

# Clean up
kill $SERVER_PID 2>/dev/null || true
```

Expected: Integration tests pass, no external API calls

---

### Step 3: Verify default test excludes external

```bash
make test
```

Expected: Runs unit + integration only, skips external tests

---

### Step 4: Verify external tests require opt-in

```bash
# Should fail without opt-in
make test-external 2>&1 | grep -i "allow_external_tests"
```

Expected: Error message about ALLOW_EXTERNAL_TESTS=1

---

### Step 5: Verify external tests work with opt-in

```bash
# This requires actual API keys to fully pass
# For verification, just check it runs without opt-in error
ALLOW_EXTERNAL_TESTS=1 make test-external 2>&1 | head -20
```

Expected: Tests start running (may skip if API keys missing)

---

### Step 6: Verify lenient mode

```bash
ALLOW_EXTERNAL_TESTS=1 EXTERNAL_TESTS_SKIP_MISSING=1 make test-external 2>&1 | head -20
```

Expected: Tests run, skipping those with missing keys

---

### Step 7: Verify isolation guards

```bash
# Create a temporary unit test that makes a real HTTP call
cat > tests/unit/test_isolation_guard.py << 'EOF'
import pytest
import httpx

@pytest.mark.unit
async def test_unit_with_real_http():
    """This should fail isolation guard."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://example.com")
        assert response.status_code == 200
EOF

# Run the test - should fail with isolation guard error
pytest tests/unit/test_isolation_guard.py -v 2>&1 | grep -i "must use"

# Clean up
rm tests/unit/test_isolation_guard.py
```

Expected: Test fails with isolation guard message

---

### Step 8: Verify marker auto-application

```bash
# Check that external tests get the marker automatically
pytest --collect-only tests/external/ 2>&1 | grep -A 2 "test_zaio_basic_chat"
```

Expected: Shows `external` marker applied

---

### Step 9: Verify help output

```bash
make help | grep -A 15 "Testing:"
```

Expected: Shows all new test targets

---

### Step 10: Clean up and final commit

```bash
# Make sure no test artifacts remain
make clean

# Final verification that default behavior is preserved
make test
```

Expected: All unit and integration tests pass

---

## Summary

After completing all tasks, you will have:

1. ✅ `tests/external/` directory with proper configuration
2. ✅ New `@pytest.mark.external` marker (replacing `@pytest.mark.e2e`)
3. ✅ Isolation guards preventing category boundary violations
4. ✅ ZAI and ZAIO tests migrated to `tests/external/`
5. ✅ Updated Makefile targets with opt-in requirements
6. ✅ Updated documentation

**Verification Commands:**
```bash
# Verify all tests still work
make test

# Verify external tests require opt-in
make test-external  # Should fail

# Verify external tests work with opt-in
ALLOW_EXTERNAL_TESTS=1 make test-external-oneshot

# Verify isolation
make test-unit  # Should have no network calls
```

**Developer Experience:**
- Day-to-day: `make test` (fast, no API costs)
- Full validation: `make test-all` (with opt-in)
- Provider-specific: `pytest -m external -k zaio`
