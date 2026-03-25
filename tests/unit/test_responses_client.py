"""Unit tests for ResponsesAPIClient.

Test coverage:
  - Happy-path streaming (yields SSE lines + [DONE] sentinel)
  - Host-pinning warning for non-chatgpt.com URLs
  - Per-request header isolation (no cross-contamination)
  - Authorization / chatgpt-account-id never appear in log output
  - HTTP 4xx/5xx errors become HTTPException with correct status
  - Timeout errors propagate as-is (SSE wrapper handles them)
  - Network errors become HTTPException 502
  - stream=True is enforced unconditionally (caller can't forget)
  - OAuth not configured raises ValueError
  - ClientFactory creates ResponsesAPIClient for api_format='responses'
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from src.core.responses_client import _SAFE_HOST_SUFFIX, ResponsesAPIClient, _token_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHATGPT_BASE_URL = "https://chatgpt.com/backend-api"
_RESPONSES_URL = f"{_CHATGPT_BASE_URL}/v1/responses"


def _make_token_manager(
    access_token: str = "tok_test_abc",
    account_id: str = "acct_123",
) -> MagicMock:
    """Create a fake TokenManager that returns deterministic credentials."""
    mgr = MagicMock()
    mgr.get_access_token.return_value = (access_token, account_id)
    return mgr


def _make_client(
    base_url: str = _CHATGPT_BASE_URL,
    access_token: str = "tok_test_abc",
    account_id: str = "acct_123",
) -> ResponsesAPIClient:
    """Convenience factory for ResponsesAPIClient in tests."""
    return ResponsesAPIClient(
        base_url=base_url,
        timeout=10,
        oauth_token_manager=_make_token_manager(access_token, account_id),
    )


def _sse_response(lines: list[str], status: int = 200) -> httpx.Response:
    """Build a fake streaming SSE httpx.Response from a list of SSE lines."""
    body = "\n".join(lines) + "\n"
    return httpx.Response(
        status_code=status,
        headers={"content-type": "text/event-stream"},
        content=body.encode(),
    )


# ---------------------------------------------------------------------------
# OAuth / credential tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResponsesAPIClientOAuth:
    """OAuth credential handling and header building."""

    def test_no_oauth_raises_value_error_on_header_build(self):
        """Without a token manager, _build_request_headers raises ValueError.

        This ensures that misconfigured providers (forgot 'vdm oauth login')
        get a clear diagnostic instead of a cryptic AttributeError.
        """
        client = ResponsesAPIClient(
            base_url=_CHATGPT_BASE_URL,
            timeout=10,
            oauth_token_manager=None,
        )
        with pytest.raises(ValueError, match="OAuth authentication not available"):
            client._build_request_headers()

    def test_headers_contain_correct_chatgpt_account_id(self):
        """chatgpt-account-id header must use the value from the token manager.

        This tests the CRITICAL distinction: the Responses API requires
        'chatgpt-account-id', NOT the generic 'x-account-id' that
        OAuthClientMixin._inject_oauth_headers() sets.
        """
        client = _make_client(account_id="acct_xyz_789")
        headers = client._build_request_headers()

        assert "chatgpt-account-id" in headers
        assert headers["chatgpt-account-id"] == "acct_xyz_789"
        # Generic OAuth header must NOT be present
        assert "x-account-id" not in headers

    def test_headers_contain_authorization_bearer(self):
        """Authorization header must be 'Bearer <token>'."""
        client = _make_client(access_token="my_bearer_token")
        headers = client._build_request_headers()

        assert headers["Authorization"] == "Bearer my_bearer_token"

    def test_headers_contain_openai_beta(self):
        """OpenAI-Beta header must be 'responses=experimental'."""
        client = _make_client()
        headers = client._build_request_headers()

        assert headers.get("OpenAI-Beta") == "responses=experimental"

    def test_headers_contain_session_id_uuid(self):
        """Each header build must include a non-empty session_id."""
        import re

        client = _make_client()
        h1 = client._build_request_headers()
        h2 = client._build_request_headers()

        uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        assert uuid_re.match(h1["session_id"]), f"Not a UUID: {h1['session_id']}"
        assert uuid_re.match(h2["session_id"]), f"Not a UUID: {h2['session_id']}"

    def test_session_id_is_unique_per_call(self):
        """Every call to _build_request_headers must produce a fresh session_id.

        Reusing session IDs could cause upstream to reject the second request
        as a replay (or merge two distinct conversations in their logs).
        """
        client = _make_client()
        ids = {client._build_request_headers()["session_id"] for _ in range(20)}
        assert len(ids) == 20, "session_id must be unique per call"

    def test_headers_are_fresh_dict_each_call(self):
        """Each _build_request_headers() call must return a new dict object.

        Returning the same mutable dict would allow concurrent requests to
        mutate each other's headers (the cross-contamination bug this design
        explicitly prevents).
        """
        client = _make_client()
        h1 = client._build_request_headers()
        h2 = client._build_request_headers()
        assert h1 is not h2

    def test_custom_headers_are_merged(self):
        """Custom headers from config must appear in every request."""
        client = ResponsesAPIClient(
            base_url=_CHATGPT_BASE_URL,
            timeout=10,
            custom_headers={"x-my-custom": "value123"},
            oauth_token_manager=_make_token_manager(),
        )
        headers = client._build_request_headers()
        assert headers["x-my-custom"] == "value123"


# ---------------------------------------------------------------------------
# Host-pinning / safety warning tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResponsesAPIClientHostPinning:
    """Bearer tokens should only go to *.chatgpt.com (warn otherwise)."""

    def test_safe_host_no_warning(self, caplog):
        """chatgpt.com host must NOT trigger the safety warning."""
        with caplog.at_level(logging.WARNING, logger="src.core.responses_client"):
            ResponsesAPIClient(
                base_url="https://chatgpt.com/backend-api",
                oauth_token_manager=_make_token_manager(),
            )
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert not warning_records, f"Unexpected warnings: {warning_records}"

    def test_unsafe_host_emits_warning(self, caplog):
        """A non-chatgpt.com host must trigger a WARNING (but not block)."""
        with caplog.at_level(logging.WARNING, logger="src.core.responses_client"):
            client = ResponsesAPIClient(
                base_url="http://localhost:8080",
                oauth_token_manager=_make_token_manager(),
            )
        # Client is still created (not blocked)
        assert isinstance(client, ResponsesAPIClient)
        # Warning was emitted
        assert any(_SAFE_HOST_SUFFIX in record.message for record in caplog.records), (
            "Expected host-pinning warning not found in log records"
        )

    def test_non_chatgpt_production_url_warns(self, caplog):
        """Non-chatgpt.com production URLs must also warn."""
        with caplog.at_level(logging.WARNING, logger="src.core.responses_client"):
            ResponsesAPIClient(
                base_url="https://api.openai.com/v1",
                oauth_token_manager=_make_token_manager(),
            )
        assert any("chatgpt.com" in record.message for record in caplog.records), (
            "Expected chatgpt.com warning for non-chatgpt URL"
        )


# ---------------------------------------------------------------------------
# Streaming happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestResponsesAPIClientStreaming:
    """Happy-path streaming behaviour."""

    async def test_streams_sse_lines_and_done_sentinel(self):
        """Upstream SSE lines must be yielded, then 'data: [DONE]' is appended."""
        client = _make_client()

        sse_body = (
            'data: {"type": "response.created", "response": {}}\n'
            'data: {"type": "response.output_item.added"}\n'
            'data: {"type": "response.completed"}\n'
        )
        mock_response = httpx.Response(
            status_code=200,
            headers={"content-type": "text/event-stream"},
            content=sse_body.encode(),
        )

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(return_value=mock_response)

            lines = [line async for line in client.stream_responses({"model": "gpt-4o"})]

        # All three data lines from upstream
        assert 'data: {"type": "response.created", "response": {}}' in lines
        assert 'data: {"type": "response.output_item.added"}' in lines
        assert 'data: {"type": "response.completed"}' in lines
        # Sentinel appended by our client
        assert "data: [DONE]" in lines
        # Sentinel is the last item
        assert lines[-1] == "data: [DONE]"

    async def test_blank_lines_are_filtered_out(self):
        """Blank / whitespace-only SSE lines must not be yielded to the caller.

        SSE protocol uses blank lines as chunk separators; yielding them would
        cause the downstream parser to choke on unexpected empty data items.
        """
        client = _make_client()

        sse_body = (
            "\n"  # blank
            "data: event-one\n"
            "\n"  # blank
            "data: event-two\n"
            "\n"  # blank
        )
        mock_response = httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_body.encode(),
        )

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(return_value=mock_response)

            lines = [line async for line in client.stream_responses({"model": "gpt-4o"})]

        assert "" not in lines
        assert "  " not in lines
        assert "data: event-one" in lines
        assert "data: event-two" in lines

    async def test_stream_enforces_stream_true(self):
        """stream=True must be injected into the request even if caller omits it.

        The Responses API rejects requests without stream=True.  The client
        enforces this so callers cannot accidentally forget.
        """
        client = _make_client()
        captured_request: dict[str, Any] = {}

        async def capture_and_respond(request: httpx.Request) -> httpx.Response:
            import json as _json

            captured_request.update(_json.loads(request.content))
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"data: ok\n",
            )

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(side_effect=capture_and_respond)

            # Pass stream=False explicitly — the client must override it
            async for _ in client.stream_responses({"model": "gpt-4o", "stream": False}):
                pass

        assert captured_request.get("stream") is True, (
            "Client must enforce stream=True regardless of what the caller sends"
        )

    async def test_correct_url_is_called(self):
        """The client must POST to {base_url}/v1/responses."""
        client = _make_client()

        called_urls: list[str] = []

        async def capture_url(request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"data: ok\n",
            )

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(side_effect=capture_url)
            async for _ in client.stream_responses({"model": "gpt-4o"}):
                pass

        assert len(called_urls) == 1
        assert called_urls[0] == _RESPONSES_URL


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
class TestResponsesAPIClientErrors:
    """HTTP errors, timeouts, and network failures."""

    async def test_401_becomes_http_exception_401(self):
        """401 Unauthorized from upstream must become HTTPException(status_code=401)."""
        from fastapi import HTTPException

        client = _make_client()
        error_body = {"error": {"type": "authentication_error", "message": "Invalid token"}}

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(return_value=httpx.Response(401, json=error_body))

            with pytest.raises(HTTPException) as exc_info:
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

        assert exc_info.value.status_code == 401
        # The structured error body should be propagated
        detail = exc_info.value.detail
        assert detail == error_body or (
            isinstance(detail, str) and "authentication_error" in detail
        )

    async def test_429_becomes_http_exception_429(self):
        """429 Rate Limited must become HTTPException(status_code=429)."""
        from fastapi import HTTPException

        client = _make_client()

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(
                return_value=httpx.Response(429, json={"error": "rate_limited"})
            )

            with pytest.raises(HTTPException) as exc_info:
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

        assert exc_info.value.status_code == 429

    async def test_500_becomes_http_exception_500(self):
        """500 Internal Server Error must become HTTPException(status_code=500)."""
        from fastapi import HTTPException

        client = _make_client()

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )

            with pytest.raises(HTTPException) as exc_info:
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

        assert exc_info.value.status_code == 500

    async def test_read_timeout_propagates_as_is(self):
        """ReadTimeout must propagate without conversion.

        The SSE error wrapper in streaming.py converts timeout errors into
        graceful SSE error events.  If we converted to HTTPException here,
        that wrapper would never see the timeout and clients would get a
        broken connection instead of a clean error event.
        """
        client = _make_client()

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(
                side_effect=httpx.ReadTimeout("read timed out", request=None)
            )

            with pytest.raises(httpx.ReadTimeout):
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

    async def test_connect_timeout_propagates_as_is(self):
        """ConnectTimeout must also propagate without conversion."""
        client = _make_client()

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(
                side_effect=httpx.ConnectTimeout("connect timed out", request=None)
            )

            with pytest.raises(httpx.ConnectTimeout):
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

    async def test_connect_error_becomes_http_502(self):
        """Connection errors (DNS / refused) must become HTTPException(502)."""
        from fastapi import HTTPException

        client = _make_client()

        with respx.mock(assert_all_mocked=True) as respx_mock:
            respx_mock.post(_RESPONSES_URL).mock(
                side_effect=httpx.ConnectError("connection refused")
            )

            with pytest.raises(HTTPException) as exc_info:
                async for _ in client.stream_responses({"model": "gpt-4o"}):
                    pass

        assert exc_info.value.status_code == 502
        assert "network error" in str(exc_info.value.detail).lower()


# ---------------------------------------------------------------------------
# Security: secrets must never appear in logs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResponsesAPIClientLogSecurity:
    """Sensitive values must not appear in log output."""

    def test_token_hash_does_not_contain_original_token(self):
        """_token_hash must return a non-reversible prefix, not the original token."""
        original = "super_secret_bearer_token_xyz"
        hashed = _token_hash(original)

        assert original not in hashed
        assert len(hashed) == 8  # First 8 chars of SHA-256 hex

    def test_token_hash_is_stable(self):
        """Same token must always produce the same hash (for incident correlation)."""
        token = "stable_token_abc"
        assert _token_hash(token) == _token_hash(token)

    @pytest.mark.asyncio
    async def test_authorization_header_not_logged(self, caplog):
        """The Authorization header value must NEVER appear in any log record.

        This is a security invariant: if the bearer token leaks into logs,
        an attacker with log access can impersonate the user.
        """
        access_token = "SECRET_BEARER_TOKEN_DO_NOT_LOG"
        client = _make_client(access_token=access_token)

        sse_body = b"data: ok\n"
        mock_response = httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse_body,
        )

        with (
            caplog.at_level(logging.DEBUG, logger="src.core.responses_client"),
            respx.mock(assert_all_mocked=True) as respx_mock,
        ):
            respx_mock.post(_RESPONSES_URL).mock(return_value=mock_response)

            async for _ in client.stream_responses({"model": "gpt-4o"}, request_id="test-req-1"):
                pass

        # The literal token value must not appear in any log record
        for record in caplog.records:
            assert access_token not in record.getMessage(), (
                f"SECRET BEARER TOKEN FOUND IN LOG RECORD: {record.getMessage()}"
            )

    @pytest.mark.asyncio
    async def test_account_id_not_logged(self, caplog):
        """The chatgpt-account-id value must NEVER appear in any log record."""
        account_id = "SECRET_ACCOUNT_ID_DO_NOT_LOG"
        client = _make_client(account_id=account_id)

        mock_response = httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: ok\n",
        )

        with (
            caplog.at_level(logging.DEBUG, logger="src.core.responses_client"),
            respx.mock(assert_all_mocked=True) as respx_mock,
        ):
            respx_mock.post(_RESPONSES_URL).mock(return_value=mock_response)

            async for _ in client.stream_responses({"model": "gpt-4o"}):
                pass

        for record in caplog.records:
            assert account_id not in record.getMessage(), (
                f"SECRET ACCOUNT ID FOUND IN LOG RECORD: {record.getMessage()}"
            )


# ---------------------------------------------------------------------------
# ClientFactory integration: responses format → ResponsesAPIClient
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientFactoryResponsesFormat:
    """ClientFactory must create ResponsesAPIClient for api_format='responses'."""

    def test_factory_creates_responses_api_client_for_responses_format(self):
        """ClientFactory.get_or_create_client() must return ResponsesAPIClient.

        This is the contract that wires provider discovery to the correct HTTP
        client implementation.  Breaking this means all ChatGPT requests fall
        back to OpenAIClient (which would fail to target /v1/responses).
        """
        from src.core.provider.client_factory import ClientFactory
        from src.core.provider_config import ProviderConfig
        from src.core.responses_client import ResponsesAPIClient

        factory = ClientFactory()
        config = ProviderConfig(
            name="chatgpt",
            api_key="!OAUTH",  # OAuth mode
            base_url="https://chatgpt.com/backend-api",
            api_format="responses",
        )

        # Patch TokenManager and FileSystemAuthStorage so we don't need real OAuth files
        with (
            patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
            patch("src.core.provider.client_factory.FileSystemAuthStorage") as mock_storage_cls,
        ):
            mock_storage_cls.return_value = MagicMock()
            mock_tm_cls.return_value = MagicMock()

            client = factory.get_or_create_client(config)

        assert isinstance(client, ResponsesAPIClient), (
            f"Expected ResponsesAPIClient, got {type(client).__name__}"
        )

    def test_factory_does_not_create_responses_client_for_openai_format(self):
        """api_format='openai' must still create OpenAIClient (no regression)."""
        from src.core.client import OpenAIClient
        from src.core.provider.client_factory import ClientFactory
        from src.core.provider_config import ProviderConfig

        factory = ClientFactory()
        config = ProviderConfig(
            name="myopenai",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            api_format="openai",
        )

        client = factory.get_or_create_client(config)
        assert isinstance(client, OpenAIClient)

    def test_factory_does_not_create_responses_client_for_anthropic_format(self):
        """api_format='anthropic' must still create AnthropicClient (no regression)."""
        from src.core.anthropic_client import AnthropicClient
        from src.core.provider.client_factory import ClientFactory
        from src.core.provider_config import ProviderConfig

        factory = ClientFactory()
        config = ProviderConfig(
            name="myanthropic",
            api_key="sk-ant-test-key",
            base_url="https://api.anthropic.com",
            api_format="anthropic",
        )

        client = factory.get_or_create_client(config)
        assert isinstance(client, AnthropicClient)

    def test_factory_caches_responses_client(self):
        """get_or_create_client() must return the same instance on repeat calls."""
        from src.core.provider.client_factory import ClientFactory
        from src.core.provider_config import ProviderConfig

        factory = ClientFactory()
        config = ProviderConfig(
            name="chatgpt2",
            api_key="!OAUTH",
            base_url="https://chatgpt.com/backend-api",
            api_format="responses",
        )

        with (
            patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
            patch("src.core.provider.client_factory.FileSystemAuthStorage") as mock_storage_cls,
        ):
            mock_storage_cls.return_value = MagicMock()
            mock_tm_cls.return_value = MagicMock()

            c1 = factory.get_or_create_client(config)
            c2 = factory.get_or_create_client(config)

        assert c1 is c2, "ClientFactory must cache and return the same client instance"
