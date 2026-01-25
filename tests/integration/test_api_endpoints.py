"""Integration tests for API endpoints."""

import os

import httpx
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get test port from environment or use default (matching development server)
TEST_PORT = int(os.environ.get("VDM_TEST_PORT", "8082"))
BASE_URL = f"http://localhost:{TEST_PORT}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    import yaml

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

        assert response.status_code == 200
        # Verify content type is YAML
        assert "text/yaml" in response.headers.get("content-type", "")
        # Verify it displays inline (not as attachment)
        content_disposition = response.headers.get("content-disposition", "")
        assert "inline" in content_disposition

        # Parse YAML response
        data = yaml.safe_load(response.text)
        assert "status" in data
        # Accept both "healthy" and "ok" status values for flexibility
        assert data["status"] in ["healthy", "ok", "degraded"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_models_endpoint():
    """Test /v1/models endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/v1/models")

        # NOTE: integration tests run against an already-running server.
        # If the server binary isn't restarted after code changes, it may return `null`.
        assert response.status_code == 200
        data = response.json()
        assert data is not None

        # Default is Anthropic schema (Claude consumes this endpoint)
        assert "data" in data
        assert isinstance(data["data"], list)
        # Pagination helper keys are optional; tolerate servers that omit them.
        if "data" and isinstance(data.get("data"), list) and data.get("data"):
            assert "first_id" not in data or isinstance(data.get("first_id"), str)
            assert "last_id" not in data or isinstance(data.get("last_id"), str)
            assert "has_more" not in data or isinstance(data.get("has_more"), bool)

        # OpenAI format is available
        response_openai = await client.get(f"{BASE_URL}/v1/models?format=openai")
        assert response_openai.status_code == 200
        data_openai = response_openai.json()
        assert data_openai is not None
        assert data_openai.get("object") == "list"
        assert isinstance(data_openai.get("data"), list)

        # Raw format is available
        response_raw = await client.get(f"{BASE_URL}/v1/models?format=raw")
        assert response_raw.status_code == 200
        assert response_raw.json() is not None
        assert isinstance(response_raw.json(), dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logs_endpoint():
    """Test GET /metrics/logs endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/metrics/logs")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        assert "systemd" in data
        assert "errors" in data
        assert "traces" in data

        systemd = data["systemd"]
        assert isinstance(systemd, dict)
        assert "requested" in systemd
        assert "effective" in systemd
        assert "handler" in systemd

        assert isinstance(data["errors"], list)
        assert isinstance(data["traces"], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_running_totals_endpoint():
    """Test GET /metrics/running-totals endpoint."""
    async with httpx.AsyncClient() as client:
        # Test without filters
        response = await client.get(f"{BASE_URL}/metrics/running-totals")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"

        yaml_content = response.text

        # If metrics are disabled, we get a different response
        if "Request metrics logging is disabled" in yaml_content:
            assert "Set LOG_REQUEST_METRICS=true to enable tracking" in yaml_content
        else:
            # Check for YAML structure elements
            assert "# Running Totals Report" in yaml_content
            assert "summary:" in yaml_content
            assert "total_requests:" in yaml_content
            assert "total_errors:" in yaml_content
            assert "total_input_tokens:" in yaml_content
            assert "total_output_tokens:" in yaml_content
            assert "active_requests:" in yaml_content
            assert "average_duration_ms:" in yaml_content

            # New provider schema (explicit rollup + per-model split).
            # NOTE: Integration tests assume the running server is the code under test.
            # If you're running an older server binary, these assertions will fail.
            assert "providers:" in yaml_content
            # rollup: and models: only appear when providers have data
            if "providers: {}" not in yaml_content:
                assert "rollup:" in yaml_content
                assert "models:" in yaml_content
                # Streaming split keys
                assert "total:" in yaml_content

            # Nested mirrored metric keys
            assert "requests:" in yaml_content
            assert "errors:" in yaml_content
            assert "input_tokens:" in yaml_content
            assert "output_tokens:" in yaml_content
            assert "cache_read_tokens:" in yaml_content
            assert "cache_creation_tokens:" in yaml_content
            assert "tool_uses:" in yaml_content
            assert "tool_results:" in yaml_content
            assert "tool_calls:" in yaml_content
            assert "average_duration_ms:" in yaml_content

            # Old ambiguous nested provider totals should not appear
            # These are summary totals and are expected
            assert "total_tool_uses:" in yaml_content
            assert "total_tool_results:" in yaml_content
            assert "total_tool_calls:" in yaml_content
            assert "total_cache_read_tokens:" in yaml_content
            assert "total_cache_creation_tokens:" in yaml_content

            # Summary stays in old schema
            assert "total_requests:" in yaml_content
            assert "total_errors:" in yaml_content
            assert "total_input_tokens:" in yaml_content
            assert "total_output_tokens:" in yaml_content

        # Test with provider filter
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=poe")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if "Request metrics logging is disabled" not in yaml_content:
            assert "# Filter: provider=poe" in yaml_content

        # Test with model filter using wildcard
        response = await client.get(f"{BASE_URL}/metrics/running-totals?model=gpt*")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if "Request metrics logging is disabled" not in yaml_content:
            assert "# Filter: model=gpt*" in yaml_content

        # Test with both provider and model filter
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=poe&model=claude*")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if "Request metrics logging is disabled" not in yaml_content:
            assert "# Filter: provider=poe & model=claude*" in yaml_content

        # Test case-insensitive matching
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=POE")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connection_test():
    """Test connection test endpoint.

    This test verifies the /test-connection endpoint responds correctly,
    regardless of whether the upstream API is actually reachable.

    The endpoint may return:
    - 200 with status="success" if API is reachable
    - 200 with status="skipped" for passthrough providers
    - 503 with status="failed" if API is unreachable
    - 429 if rate limited by upstream provider
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/test-connection")

        # Endpoint should respond with 200 (success/skipped), 503 (failed), or 429 (rate limited)
        assert response.status_code in (200, 503, 429)

        # 429 responses have a different structure (FastAPI rate limiting)
        if response.status_code == 429:
            data = response.json()
            assert "detail" in data
            return

        data = response.json()

        # Verify response structure
        assert "status" in data
        assert data["status"] in ("success", "failed", "skipped")

        # Common fields across all response types
        assert "provider" in data or "error_type" in data

        if data["status"] == "success":
            assert "message" in data
            assert "response_id" in data
        elif data["status"] == "failed":
            assert "message" in data or "error_type" in data


# ZAIO provider tests moved to tests/external/test_zaio_provider.py
# - test_basic_chat → test_zaio_basic_chat
# - test_streaming_chat → test_zaio_streaming_chat
# - test_function_calling → test_zaio_function_calling
# - test_with_system_message → test_zaio_with_system_message
# - test_multimodal → test_zaio_multimodal
# - test_conversation_with_tool_use → test_zaio_conversation_with_tool_use
# - test_token_counting → test_zaio_token_counting


# ZAI provider test moved to tests/external/test_zai_provider.py
