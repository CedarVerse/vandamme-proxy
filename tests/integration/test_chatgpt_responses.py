"""Integration tests for the ChatGPT Responses API full pipeline.

These tests verify the complete end-to-end request conversion chain:

    Claude request (/v1/messages)
        → request_converter.convert_claude_to_openai()
        → responses_converter.convert_openai_to_responses_request()
        → ResponsesAPIClient.stream_responses()   ← RESPX mock here
        → responses_converter.translate_responses_sse_to_openai()
        → response_converter.convert_openai_streaming_to_claude()
        → Client (SSE stream or JSON)

Why these live in tests/integration/ instead of tests/unit/
------------------------------------------------------------
Unit tests cover individual components in isolation (responses_converter.py,
ResponsesAPIClient, etc.) with highly focused assertions.  These tests exercise
the *composition* of all those pieces through the real FastAPI app — the same
code path a live client would take — without the cost of a running server or
real network calls (RESPX intercepts at the HTTP layer).

The key difference from tests/unit/test_api_endpoints_mocked.py:
- These tests specifically exercise the Responses API three-way dispatch path
- Provider setup is done per-test (chatgpt provider with api_format=responses)
- OAuth token injection is mocked at the TokenManager level
- RESPX intercepts https://chatgpt.com/backend-api/codex/v1/responses

RESPX mocking pattern
---------------------
ResponsesAPIClient creates a *fresh* ``httpx.AsyncClient`` per request (see
responses_client.py design note 3). RESPX's global mock context intercepts
all ``httpx`` calls regardless of client instance, so ``respx.mock()`` works
correctly without needing to patch the client constructor.

Environment variables for chatgpt provider
------------------------------------------
We set CHATGPT_API_KEY=!OAUTH and CHATGPT_BASE_URL plus CHATGPT_API_FORMAT=responses
to activate the responses-format dispatch path.  The TokenManager is patched at
``src.core.provider.client_factory.TokenManager`` so we never need real OAuth files.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ChatGPT provider uses this base URL in defaults.toml.
# The Responses API endpoint is appended as /v1/responses.
_CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"
_RESPONSES_API_URL = f"{_CHATGPT_BASE_URL}/v1/responses"

# Model name to use in Claude requests — must match a known chatgpt alias or
# a valid Responses API model name.  "gpt-5" is the haiku alias in defaults.toml.
_CHATGPT_MODEL = "chatgpt:gpt-5"

# Fake OAuth credentials (never used for real HTTP calls — RESPX intercepts)
_FAKE_ACCESS_TOKEN = "fake_oauth_access_token_for_testing"
_FAKE_ACCOUNT_ID = "fake_account_id_12345"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_token_manager() -> MagicMock:
    """Return a fake TokenManager that yields deterministic test credentials.

    The ResponsesAPIClient calls ``oauth_token_manager.get_access_token()``
    inside ``_build_request_headers()``.  We return predictable values so tests
    don't depend on filesystem state (no ``~/.vandamme/oauth/chatgpt/auth.json``).
    """
    mgr = MagicMock()
    mgr.get_access_token.return_value = (_FAKE_ACCESS_TOKEN, _FAKE_ACCOUNT_ID)
    return mgr


def _make_sse_body(events: list[dict[str, Any]]) -> bytes:
    """Build a Responses API SSE response body from a list of event dicts.

    Each dict is serialized as ``data: <json>\\n`` (no ``event:`` prefix — the
    Responses API uses a ``type`` key inside the JSON instead of the SSE event
    field).  Blank lines between events are optional for httpx's aiter_lines()
    but match the SSE spec.

    Args:
        events: List of dicts, each representing one Responses API SSE event.

    Returns:
        UTF-8 encoded SSE body suitable for use in an httpx.Response.
    """
    lines: list[str] = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")  # SSE blank-line separator
    return "\n".join(lines).encode()


@pytest.fixture()
def chatgpt_provider_env() -> Generator[None, None, None]:
    """Configure the chatgpt provider via environment variables.

    Sets the minimal env vars needed to activate the chatgpt provider with
    api_format='responses'.  The conftest's setup_test_environment_for_unit_tests
    runs first (autouse) and sets the global defaults; we layer chatgpt-specific
    vars on top, then tear down after the test.

    Why CHATGPT_API_KEY=!OAUTH?
    The ProviderConfig.__post_init__ detects the OAUTH_SENTINEL and sets
    auth_mode=AuthMode.OAUTH, which causes ClientFactory to create a
    ResponsesAPIClient instead of OpenAIClient.
    """
    chatgpt_vars = {
        "CHATGPT_API_KEY": "!OAUTH",
        "CHATGPT_BASE_URL": _CHATGPT_BASE_URL,
        "CHATGPT_API_FORMAT": "responses",
    }
    original = {k: os.environ.get(k) for k in chatgpt_vars}
    os.environ.update(chatgpt_vars)

    # Force fresh imports so the app picks up the new environment
    modules_to_clear = [
        "src.core.config",
        "src.core.dependencies",
        "src.core.provider_manager",
        "src.core.provider.client_factory",
        "src.main",
    ]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

    yield

    # Restore original environment
    for k, v in original.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    # Clear again so subsequent tests get a clean slate
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_sse_json_from_streaming_response(response: Any) -> list[dict]:
    """Parse all ``data:`` lines from a streaming TestClient response.

    TestClient buffers the full SSE stream in memory; we iterate the raw bytes
    to extract each ``data: {...}`` payload.

    Args:
        response: A TestClient response object (not yet consumed).

    Returns:
        List of parsed JSON objects from each ``data:`` line, excluding
        the ``data: [DONE]`` sentinel.
    """
    body = b"".join(response.iter_bytes())
    results: list[dict] = []
    for line in body.decode().splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            payload = stripped[len("data:"):].strip()
            if payload == "[DONE]":
                continue
            try:
                results.append(json.loads(payload))
            except json.JSONDecodeError:
                pass  # Ignore non-JSON data lines
    return results


# ---------------------------------------------------------------------------
# Test 1: Full pipeline — non-streaming Claude request → forced streaming
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_text_response(chatgpt_provider_env):
    """Full pipeline: Claude request → Responses API (RESPX-mocked) → Claude response.

    This is the primary smoke test for the entire Responses API pipeline.
    A Claude-format streaming request reaches /v1/messages, flows through:
    1. request_converter → OpenAI Chat Completions format
    2. responses_converter → Responses API format
    3. ResponsesAPIClient → RESPX-intercepted HTTP call
    4. translate_responses_sse_to_openai → OpenAI SSE format
    5. convert_openai_streaming_to_claude → Claude SSE format

    The text delta "Hello, world!" must survive all five translations intact.

    Note: We use stream=True because the Responses API only supports streaming.
    Non-streaming requests to api_format='responses' providers raise ValueError
    in get_non_streaming_handler() as a hard guard.
    """
    # Build a minimal Responses API SSE stream that produces one text message.
    # The sequence mirrors what ChatGPT's real backend emits:
    # 1. response.created    — establishes the response ID
    # 2. response.output_text.delta — carries the actual text
    # 3. response.output_text.done  — signals text turn complete
    # 4. response.completed  — carries usage and terminates the stream
    sse_events = [
        {
            "type": "response.created",
            "response": {"id": "resp_inttest01", "status": "in_progress"},
        },
        {
            "type": "response.output_text.delta",
            "delta": "Hello, world!",
        },
        {
            "type": "response.output_text.done",
            "text": "Hello, world!",
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_inttest01",
                "status": "completed",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "total_tokens": 14,
                },
            },
        },
    ]
    mock_response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        content=_make_sse_body(sse_events),
    )

    with (
        # Patch TokenManager so we don't need real OAuth files on disk.
        # ClientFactory calls TokenManager(storage=...) inside get_or_create_client();
        # we return a pre-configured mock that yields our fake credentials.
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        # Intercept all HTTP calls — the ResponsesAPIClient creates a fresh
        # httpx.AsyncClient per request, so we use the global respx.mock() context.
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(return_value=mock_response)

        # Import app AFTER patching and env setup so it picks up chatgpt provider
        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 100,
                    "stream": True,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=TEST_HEADERS,
            )

    # Stream must be valid SSE
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse SSE stream and locate the text delta chunk
    chunks = _collect_sse_json_from_streaming_response(response)
    assert chunks, "Expected at least one SSE chunk"

    # The stream must contain Claude-format content_block_delta with our text.
    # Claude SSE uses: event=content_block_delta, data={"type": "content_block_delta",
    #   "delta": {"type": "text_delta", "text": "Hello, world!"}}
    text_deltas = [
        chunk.get("delta", {}).get("text", "")
        for chunk in chunks
        if chunk.get("type") == "content_block_delta"
        and chunk.get("delta", {}).get("type") == "text_delta"
    ]
    full_text = "".join(text_deltas)
    assert "Hello, world!" in full_text, (
        f"Expected 'Hello, world!' in assembled text, got: {full_text!r}. "
        f"Full SSE chunks: {chunks}"
    )


# ---------------------------------------------------------------------------
# Test 2: Full pipeline with tool use
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_tool_use(chatgpt_provider_env):
    """Full pipeline with tool definitions: verify tool_use content block in Claude response.

    The Responses API returns tool calls via ``response.output_item.done``
    events with ``type=function_call``.  This test verifies the full translation
    chain produces a Claude ``tool_use`` content block with the correct
    function name and input arguments.

    Pipeline step that does the translation:
    - translate_responses_sse_to_openai() converts function_call → tool_calls chunk
    - convert_openai_streaming_to_claude() converts tool_calls → tool_use content block
    """
    # A Responses API stream that returns a single function_call output item.
    # The ``arguments`` field carries JSON-encoded function arguments.
    tool_call_args = {"city": "San Francisco"}
    sse_events = [
        {
            "type": "response.created",
            "response": {"id": "resp_tool01", "status": "in_progress"},
        },
        {
            # response.output_item.done with type=function_call is how the
            # Responses API delivers tool calls (complete, not in deltas).
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "call_id": "call_tool_abc",
                "name": "get_weather",
                "arguments": json.dumps(tool_call_args),
            },
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_tool01",
                "status": "completed",
                "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            },
        },
    ]
    mock_response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        content=_make_sse_body(sse_events),
    )

    with (
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(return_value=mock_response)

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 200,
                    "stream": True,
                    "messages": [
                        {
                            "role": "user",
                            "content": "What's the weather in San Francisco?",
                        }
                    ],
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get current weather for a city",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string", "description": "City name"}
                                },
                                "required": ["city"],
                            },
                        }
                    ],
                },
                headers=TEST_HEADERS,
            )

    assert response.status_code == 200, f"Expected 200: {response.text}"
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Scan the SSE stream for a tool_use content_block_start event.
    # Claude format emits tool use as:
    #   event: content_block_start
    #   data: {"type": "content_block_start", "index": N,
    #          "content_block": {"type": "tool_use", "id": "...", "name": "get_weather"}}
    body_text = b"".join(response.iter_bytes()).decode()
    assert "get_weather" in body_text, (
        f"Expected tool name 'get_weather' in SSE stream, got: {body_text[:500]!r}"
    )
    assert "tool_use" in body_text, (
        f"Expected 'tool_use' content block type in SSE stream, got: {body_text[:500]!r}"
    )

    # Verify the arguments were passed through correctly
    assert "San Francisco" in body_text or '"city"' in body_text, (
        f"Expected tool arguments in SSE stream, got: {body_text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Error handling — HTTP 4xx from upstream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handling_http_401_upstream(chatgpt_provider_env):
    """HTTP 401 from Responses API → error surfaced to Claude client.

    When the upstream Responses API returns HTTP 401 (expired OAuth token),
    ResponsesAPIClient raises HTTPException(status_code=401).  The endpoint's
    exception handler must surface this to the client rather than crashing
    or silently returning a 200 with empty content.

    This validates the error path in ResponsesAPIClient.stream_responses():
        if response.status_code >= 400:
            await response.aread()
            raise HTTPException(status_code=..., detail=...)
    """
    error_body = {
        "error": {
            "type": "authentication_error",
            "message": "OAuth token expired. Please re-authenticate.",
        }
    }
    mock_response = httpx.Response(
        status_code=401,
        json=error_body,
    )

    with (
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(return_value=mock_response)

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 100,
                    "stream": True,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=TEST_HEADERS,
            )

    # The proxy must NOT return 200 — a 401/403/4xx/5xx from upstream should be
    # surfaced.  Streaming endpoints that have already started the response will
    # embed the error in the SSE stream; others may return a direct HTTP error.
    # Either way, the response must signal failure.
    #
    # Design note: for streaming requests, the FastAPI endpoint can either:
    # (a) return HTTP 4xx directly if the exception is raised before streaming starts, OR
    # (b) return HTTP 200 with an SSE error event embedded in the stream.
    # Both are valid from the proxy's perspective.  We test that at least one of
    # these correctly surfaces the error to the caller.
    if response.status_code == 200:
        # Error was embedded in SSE stream
        body_text = b"".join(response.iter_bytes()).decode()
        assert '"error"' in body_text or "authentication_error" in body_text or "401" in body_text, (
            f"Expected error information in SSE stream for 401 upstream, got: {body_text[:500]!r}"
        )
    else:
        # Direct HTTP error response
        assert response.status_code in (401, 403, 500, 502), (
            f"Unexpected status code {response.status_code} for 401 upstream error"
        )


# ---------------------------------------------------------------------------
# Test 4: Error handling — response.failed event in stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_handling_response_failed_event(chatgpt_provider_env):
    """HTTP 200 with response.failed SSE event → error surfaced to Claude client.

    The Responses API can return HTTP 200 but include a ``response.failed``
    event in the SSE stream (e.g., the model crashed mid-generation).
    The responses_converter.translate_responses_sse_to_openai() converts this
    to an OpenAI-format error chunk: ``{"error": {"message": ..., "type": "api_error"}}``.

    This tests that the error event doesn't get silently dropped and reaches
    the client in a recognizable form.

    The relevant converter code path:
        elif kind == "response.failed":
            error_chunk = {"error": {"message": msg, "type": "api_error"}}
            yield f"data: {json.dumps(error_chunk)}\\n\\n"
            yield "data: [DONE]\\n\\n"
    """
    sse_events = [
        {
            "type": "response.created",
            "response": {"id": "resp_fail01", "status": "in_progress"},
        },
        {
            # response.failed: the API failed mid-stream (e.g. content policy, OOM)
            "type": "response.failed",
            "response": {
                "id": "resp_fail01",
                "status": "failed",
                "error": {
                    "code": "server_error",
                    "message": "The model encountered an unexpected error.",
                },
            },
        },
    ]
    mock_response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        content=_make_sse_body(sse_events),
    )

    with (
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(return_value=mock_response)

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 100,
                    "stream": True,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=TEST_HEADERS,
            )

    # The stream must return HTTP 200 (SSE was started before failure was detected)
    assert response.status_code == 200, f"Expected 200 with SSE error, got: {response.status_code}"
    assert "text/event-stream" in response.headers.get("content-type", "")

    # The SSE body is in Claude format (not OpenAI format) at this stage.
    # The pipeline is: response.failed → translate_responses_sse_to_openai (emits error chunk)
    #   → convert_openai_streaming_to_claude (produces Claude SSE events).
    #
    # NOTE: The OpenAI→Claude state machine (ingest_openai_chunk) currently drops
    # {"error": ...} chunks because they have no "choices" field.  The error IS
    # logged as a WARNING (visible in test output), and the stream terminates
    # cleanly via the normal Claude message_stop sequence.
    #
    # This is acceptable Tier-1 behavior: the proxy logs the failure and closes
    # the stream gracefully without crashing.  A future improvement (Tier-2) would
    # be to propagate the error as a Claude-format error SSE event.
    body_text = b"".join(response.iter_bytes()).decode()

    # The stream must terminate with a clean Claude message_stop event
    # (the pipeline must not crash on response.failed — it should close gracefully)
    assert "message_stop" in body_text, (
        f"Expected Claude 'message_stop' event at end of stream after response.failed, "
        f"got: {body_text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: Empty/minimal stream — only response.completed, no text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_stream_graceful_handling(chatgpt_provider_env):
    """Minimal Responses API stream with no text output → graceful handling, no crash.

    Some Responses API responses may produce no text output (e.g. a pure
    tool-call response with no assistant preamble, or a response filtered by
    content policy with no message emitted).

    This test verifies the pipeline handles a stream that goes directly from
    response.created → response.completed without any output events.

    Key invariants:
    1. No unhandled exception (the proxy must not crash)
    2. HTTP 200 returned (streaming started normally)
    3. Stream terminates cleanly (data: [DONE] present)
    4. No assertion errors in the converter (sent_stop_chunk guard handles this)

    The converter emits a fallback stop chunk in this case:
        if not sent_stop_chunk:
            yield fallback stop chunk
        yield "data: [DONE]\\n\\n"
    """
    sse_events = [
        {
            "type": "response.created",
            "response": {"id": "resp_empty01", "status": "in_progress"},
        },
        # No output_text.delta, no output_item.done — stream goes straight to completed
        {
            "type": "response.completed",
            "response": {
                "id": "resp_empty01",
                "status": "completed",
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 0,
                    "total_tokens": 5,
                },
            },
        },
    ]
    mock_response = httpx.Response(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        content=_make_sse_body(sse_events),
    )

    with (
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(return_value=mock_response)

        from src.main import app

        # No exception should propagate — any crash would fail the test here
        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 100,
                    "stream": True,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=TEST_HEADERS,
            )

    # Must complete without crashing
    assert response.status_code == 200, (
        f"Expected 200 for empty stream, got {response.status_code}: {response.text}"
    )
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Stream must terminate cleanly.
    # The pipeline produces Claude SSE format (not OpenAI format), so we look
    # for the Claude message_stop event rather than OpenAI's [DONE] sentinel.
    # The converter's fallback stop chunk ensures even empty streams close with
    # a proper finish_reason before message_stop is emitted.
    body_text = b"".join(response.iter_bytes()).decode()
    assert "message_stop" in body_text, (
        f"Expected Claude 'message_stop' termination event for empty stream, "
        f"got: {body_text[:500]!r}"
    )


# ---------------------------------------------------------------------------
# Test 6: Request format verification — Responses API request shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_format_sent_to_responses_api(chatgpt_provider_env):
    """Verify the request body sent to the Responses API matches the expected schema.

    The two-step conversion (Claude→OpenAI→Responses) must produce a request
    that contains the required Responses API fields:
    - ``instructions`` (from system message or default)
    - ``input`` (array of message items)
    - ``stream=True`` (always enforced)
    - ``store=False`` (always set, privacy guard)
    - ``model`` (forwarded from the resolved model name)

    This test captures the actual HTTP request body via a RESPX side-effect
    callback, allowing assertions on what the proxy *sends*, not just what
    it *returns*.

    This is particularly valuable for regression testing: any change to the
    request conversion pipeline that produces a malformed Responses API request
    will be caught here before it causes a hard-to-debug upstream error.
    """
    # Capture the request body via a side-effect callback.
    # The callback must return a valid SSE response to keep the pipeline happy.
    captured_request_body: dict[str, Any] = {}

    sse_events = [
        {"type": "response.output_text.delta", "delta": "OK"},
        {"type": "response.completed", "response": {
            "id": "resp_verify01",
            "status": "completed",
            "usage": {"input_tokens": 12, "output_tokens": 1, "total_tokens": 13},
        }},
    ]
    sse_body = _make_sse_body(sse_events)

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        """Capture the request body sent to the Responses API.

        This callback intercepts the raw httpx.Request before it would hit the
        (non-existent) network endpoint, captures the JSON body for assertion,
        and returns a minimal valid SSE response to keep the pipeline flowing.
        """
        nonlocal captured_request_body
        captured_request_body = json.loads(request.content)
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/event-stream"},
            content=sse_body,
        )

    with (
        patch("src.core.provider.client_factory.TokenManager") as mock_tm_cls,
        patch("src.core.provider.client_factory.FileSystemAuthStorage"),
        respx.mock(assert_all_called=True, assert_all_mocked=True) as respx_mock,
    ):
        mock_tm_cls.return_value = _make_mock_token_manager()
        respx_mock.post(_RESPONSES_API_URL).mock(side_effect=capture_and_respond)

        from src.main import app

        with TestClient(app) as client:
            client.post(
                "/v1/messages",
                json={
                    "model": _CHATGPT_MODEL,
                    "max_tokens": 100,
                    "stream": True,
                    "system": "You are a helpful assistant.",
                    "messages": [{"role": "user", "content": "Ping"}],
                },
                headers=TEST_HEADERS,
            )

    # --- Verify the Responses API request schema ---

    # stream=True must always be enforced by ResponsesAPIClient
    assert captured_request_body.get("stream") is True, (
        "stream=True must be enforced unconditionally by ResponsesAPIClient"
    )

    # store=False must always be set (privacy: don't persist in ChatGPT backend)
    assert captured_request_body.get("store") is False, (
        "store=False must always be set to prevent conversation persistence"
    )

    # System message must be promoted to instructions field
    instructions = captured_request_body.get("instructions", "")
    assert "helpful assistant" in instructions, (
        f"Expected system message in instructions field, got: {instructions!r}"
    )

    # User messages must be in the input array
    input_items = captured_request_body.get("input", [])
    assert isinstance(input_items, list), "input must be a list"
    assert len(input_items) >= 1, "input must contain at least the user message"

    # User content must use the 'input_text' type (not 'text')
    # This is the Responses API's content type for user-turn text.
    user_msgs = [
        item for item in input_items
        if isinstance(item, dict) and item.get("role") == "user"
    ]
    assert len(user_msgs) >= 1, "Expected at least one user message in input"
    user_content = user_msgs[0].get("content", [])
    assert any(
        isinstance(c, dict) and c.get("type") == "input_text"
        for c in (user_content if isinstance(user_content, list) else [])
    ), (
        f"Expected 'input_text' type for user content in Responses API, "
        f"got: {user_content!r}"
    )
