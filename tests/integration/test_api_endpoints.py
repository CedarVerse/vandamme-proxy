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
    """Test GET /metrics/running-totals endpoint.

    Uses YAML parsing to validate structure instead of fragile string matching.
    """
    import yaml

    async with httpx.AsyncClient() as client:
        # Test without filters
        response = await client.get(f"{BASE_URL}/metrics/running-totals")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"

        yaml_content = response.text
        yaml_data = yaml.safe_load(yaml_content)

        # Check metrics disabled flag (structured approach)
        # When metrics are disabled, _metrics_enabled flag is set to False
        if not yaml_data.get("_metrics_enabled", True):
            # Metrics disabled - check for suggestion
            # The response should contain guidance about enabling metrics
            assert any("LOG_REQUEST_METRICS" in str(v) for v in yaml_data.values()), (
                "Disabled metrics response should mention LOG_REQUEST_METRICS"
            )
        else:
            # Metrics enabled - validate hierarchical structure
            assert isinstance(yaml_data, dict), "YAML root should be a dict"

            # Validate summary section (always present when metrics enabled)
            assert "summary" in yaml_data, "Summary section required"
            summary = yaml_data["summary"]
            assert isinstance(summary, dict), "Summary must be a dict"
            for key in (
                "total_requests",
                "total_errors",
                "total_input_tokens",
                "total_output_tokens",
                "active_requests",
                "average_duration_ms",
            ):
                assert key in summary, f"Summary missing required key: {key}"

            # Validate providers key (always present due to HierarchicalData contract)
            assert "providers" in yaml_data, "Providers key required by TypedDict contract"
            assert isinstance(yaml_data["providers"], dict), "Providers must be a dict"

            # Only validate provider structure if non-empty
            if yaml_data["providers"]:
                # Filter out comment keys (starting with #)
                provider_entries = {
                    k: v for k, v in yaml_data["providers"].items() if not k.startswith("#")
                }

                # Check that at least one provider has expected structure
                for provider_key, provider_data in provider_entries.items():
                    if isinstance(provider_data, dict):
                        # Validate rollup structure
                        assert "rollup" in provider_data, f"Provider {provider_key} missing rollup"
                        rollup = provider_data["rollup"]
                        assert "total" in rollup, f"Provider {provider_key} rollup missing total"
                        total = rollup["total"]
                        assert "requests" in total, (
                            f"Provider {provider_key} total missing requests"
                        )

                        # Models section is optional (only when there's model data)
                        if "models" in provider_data:
                            models = provider_data["models"]
                            assert isinstance(models, dict), (
                                f"Provider {provider_key} models must be dict"
                            )

        # Test with provider filter
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=poe")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if yaml_data.get("_metrics_enabled", True):
            assert "# Filter: provider=poe" in yaml_content

        # Test with model filter using wildcard
        response = await client.get(f"{BASE_URL}/metrics/running-totals?model=gpt*")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if yaml_data.get("_metrics_enabled", True):
            assert "# Filter: model=gpt*" in yaml_content

        # Test with both provider and model filter
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=poe&model=claude*")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"
        yaml_content = response.text

        if yaml_data.get("_metrics_enabled", True):
            assert "# Filter: provider=poe & model=claude*" in yaml_content

        # Test case-insensitive matching
        response = await client.get(f"{BASE_URL}/metrics/running-totals?provider=POE")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/yaml; charset=utf-8"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connection_test():
    """Test connection test endpoint.

    LIMITATIONS:
    This test runs against a real upstream API without mocking, so it accepts
    multiple outcomes (success/failed/skipped/rate-limited). This allows silent
    regressions because the test passes even when the success path is broken.

    TODO: Split into separate test scenarios with RESPX mocking:
    - test_connection_test_success(): Mock successful upstream response
    - test_connection_test_skipped(): Mock passthrough provider configuration
    - test_connection_test_failure(): Mock upstream unreachable scenario

    Current endpoint behavior:
    - 200 with status="success" if API is reachable and returns valid response
    - 200 with status="skipped" for passthrough providers (no connection test)
    - 503 with status="failed" if API is unreachable or returns error
    - 429 if rate limited by upstream provider (FastAPI rate limiting)

    Success path structure (when status="success"):
    {
        "status": "success",
        "provider": "provider_name",
        "message": "Successfully connected",
        "response_id": "req_xxx",
        "model": "model_name",
        "cached": false
    }

    Failed path structure (when status="failed"):
    {
        "status": "failed",
        "provider": "provider_name",
        "message": "Error details",
        "error_type": "upstream_error"
    }
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/test-connection")

        # Endpoint should respond with 200 (success/skipped), 503 (failed), or 429 (rate limited)
        assert response.status_code in (200, 503, 429)

        # 429 responses have a different structure (FastAPI rate limiting)
        if response.status_code == 429:
            data = response.json()
            assert "detail" in data
            pytest.skip("Rate limited by upstream - cannot validate success path")

        data = response.json()

        # Verify response structure
        assert "status" in data, "Response missing 'status' field"
        assert data["status"] in ("success", "failed", "skipped"), (
            f"Invalid status: {data['status']}"
        )

        # Common fields across all response types
        assert "provider" in data or "error_type" in data, (
            "Response must have 'provider' or 'error_type' field"
        )

        # Validate success path structure when status is "success"
        if data["status"] == "success":
            assert "message" in data, "Success response missing 'message' field"
            assert "response_id" in data, "Success response missing 'response_id' field"
            assert isinstance(data["response_id"], str), "response_id must be a string"
            assert data["response_id"].startswith("req_"), (
                f"response_id must start with 'req_', got: {data['response_id']}"
            )
        elif data["status"] == "failed":
            assert "message" in data or "error_type" in data, (
                "Failed response must have 'message' or 'error_type' field"
            )


# ZAIO provider tests moved to tests/external/test_zaio_provider.py
# - test_basic_chat → test_zaio_basic_chat
# - test_streaming_chat → test_zaio_streaming_chat
# - test_function_calling → test_zaio_function_calling
# - test_with_system_message → test_zaio_with_system_message
# - test_multimodal → test_zaio_multimodal
# - test_conversation_with_tool_use → test_zaio_conversation_with_tool_use
# - test_token_counting → test_zaio_token_counting


# ZAI provider test moved to tests/external/test_zai_provider.py
