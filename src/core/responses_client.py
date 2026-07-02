"""HTTP client for the ChatGPT internal Responses API.

Why a dedicated client instead of reusing OpenAIClient/AnthropicClient?
----------------------------------------------------------------------
Neither the OpenAI SDK nor the Anthropic SDK can target the internal
``/v1/responses`` endpoint used by ChatGPT.  The endpoint is not part of
the public API surface; it requires:

  - A *Bearer* token (OAuth) rather than an ``Authorization: Bearer sk-...``
    API-key style header.
  - A ``chatgpt-account-id`` header (distinct from the generic
    ``x-account-id`` set by OAuthClientMixin).
  - ``OpenAI-Beta: responses=experimental`` to opt-in to the response format.
  - A per-request ``session_id`` UUID for request correlation.

We therefore use ``httpx.AsyncClient`` directly and create a *fresh client
per request* (Tier-1 simplicity, see design note below).

Design decisions
----------------
1. **Per-request headers via `.post()`, NOT default_headers**
   The ClientFactory caches *one* client per provider.  If sensitive headers
   (Authorization, chatgpt-account-id) lived on the shared ``default_headers``
   dict, concurrent requests from different users would cross-contaminate.
   Passing headers per-call is the only safe option for a shared httpx client.

2. **chatgpt-account-id ≠ x-account-id**
   OAuthClientMixin injects ``x-account-id`` for generic OAuth flows.  The
   Responses API specifically requires the header named ``chatgpt-account-id``.

3. **Per-request ``async with httpx.AsyncClient()``**
   A fresh context manager per call avoids lifetime-management complexity
   (no background cleanup tasks, no stale-connection footguns).  Connection
   reuse is sacrificed; this is acceptable at Tier-1 given the target is a
   ChatGPT subscription endpoint, not a high-QPS API key pool.

4. **Host pinning / warning**
   Bearer tokens should only be sent to ``*.chatgpt.com``.  We log a WARNING
   if the configured base_url does not match, so misconfigured test setups are
   visible without breaking them.

5. **No secrets in logs** — Authorization and chatgpt-account-id values are
   never logged at any level.  We only log the SHA-256 prefix of the token for
   incident correlation (same pattern as AnthropicClient).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from src.core.config.accessors import (
    log_request_metrics,
    streaming_connect_timeout,
    streaming_read_timeout,
)
from src.core.logging import ConversationLogger
from src.core.oauth_client_mixin import OAuthClientMixin

conversation_logger = ConversationLogger.get_logger()
logger = logging.getLogger(__name__)

# The Responses API always requires streaming; non-stream mode is unsupported.
# ChatGPT internal API: /responses (no /v1 prefix — that's the public OpenAI API convention)
_RESPONSES_ENDPOINT = "/responses"

# Header required by the Responses API to opt-in to the experimental format.
_BETA_HEADER = "responses=experimental"

# Hosts that are safe to send ChatGPT Bearer tokens to.
# A warning is emitted (but request not blocked) if the base_url doesn't match —
# this allows local test setups and non-prod environments to still work.
_SAFE_HOST_SUFFIX = "chatgpt.com"

NextApiKey = Callable[[set[str]], Awaitable[str]]


def _token_hash(token: str) -> str:
    """Return first-8-chars of SHA-256 hash for log correlation.

    Non-reversible, stable across runs, suitable for debugging/incident
    correlation.  Never log the full token.

    nosemgrep: py.weak-sensitive-data-hashing
    SHA-256 first-8-char is appropriate for logging correlation IDs:
    - Non-reversible: cannot recover the original bearer token
    - Stable: same token produces the same hash across runs
    - Purpose: debugging/incident correlation, not cryptography
    """
    return hashlib.sha256(token.encode()).hexdigest()[:8]


class ResponsesAPIClient(OAuthClientMixin):
    """Async HTTP client for the ChatGPT internal Responses API.

    This client is fundamentally different from OpenAIClient/AnthropicClient:
    - Uses raw httpx (no SDK wrapper) because the SDK cannot target /v1/responses
    - Always streams (non-streaming is not supported by the endpoint)
    - Requires OAuth tokens, not static API keys
    - Injects per-request headers to avoid cross-contamination between concurrent requests
    - Creates a fresh httpx.AsyncClient per call for simplicity (Tier-1 approach)

    Usage:
        client = ResponsesAPIClient(
            base_url="https://chatgpt.com/backend-api",
            timeout=90,
            oauth_token_manager=token_manager,
        )
        async for line in client.stream_responses(request_dict, request_id="abc"):
            process(line)
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 90,
        custom_headers: dict[str, str] | None = None,
        oauth_token_manager: Any | None = None,
    ) -> None:
        """Initialise a ResponsesAPIClient.

        Args:
            base_url: Base URL for the Responses API provider (e.g.
                      ``https://chatgpt.com/backend-api``).
            timeout: Non-streaming request timeout in seconds (currently unused
                     since the endpoint only supports streaming, but kept for
                     interface consistency with OpenAIClient/AnthropicClient).
            custom_headers: Additional HTTP headers to include in every request
                            (e.g. from ``CUSTOM_HEADER_*`` environment variables).
            oauth_token_manager: TokenManager instance for OAuth providers.
                                 Required for the Responses API — API key mode
                                 is not supported.
        """
        # Normalise trailing slash for consistent URL construction
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.custom_headers = custom_headers or {}

        # OAuthClientMixin contract: must expose default_api_key and
        # _oauth_token_manager for _effective_api_key and _get_oauth_token().
        self.default_api_key: str | None = None  # Responses API is OAuth-only
        self._oauth_token_manager = oauth_token_manager

        # Streaming timeout settings from global config
        self._streaming_read_timeout = streaming_read_timeout()
        self._streaming_connect_timeout = streaming_connect_timeout()

        # Warn early if the base_url looks unsafe for Bearer token injection.
        # We do NOT block — local test setups may intentionally use non-chatgpt.com URLs.
        parsed = urlparse(self.base_url)
        if not parsed.hostname or _SAFE_HOST_SUFFIX not in parsed.hostname:
            logger.warning(
                "ResponsesAPIClient: base_url host %r does not contain %r. "
                "Bearer tokens will still be sent — verify this is intentional "
                "(e.g. a local test server).  Set CHATGPT_BASE_URL to a "
                "chatgpt.com endpoint in production.",
                parsed.hostname,
                _SAFE_HOST_SUFFIX,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_request_headers(self) -> dict[str, str]:
        """Build per-request headers with injected OAuth credentials.

        IMPORTANT: Headers are built *per call*, not once at construction time.
        The ClientFactory caches one ResponsesAPIClient per provider.  If we
        stored Bearer/account-id in instance state and passed them as
        ``default_headers`` to a cached httpx.AsyncClient, concurrent requests
        would race on the shared header dict and could cross-contaminate.

        Per-call construction guarantees isolation at the cost of a small dict
        allocation per request — a worthwhile trade.

        Returns:
            A fresh headers dict ready for use in a single .post() call.

        Raises:
            ValueError: If OAuth is not configured or the token is expired/missing.
        """
        access_token, account_id = self._get_oauth_token()

        headers: dict[str, str] = {
            "content-type": "application/json",
            # Required for SSE streaming — ChatGPT API may reject without it.
            "accept": "text/event-stream",
            # CRITICAL: chatgpt-account-id is NOT x-account-id.
            # OAuthClientMixin._inject_oauth_headers() sets x-account-id for generic
            # OAuth flows, but the Responses API requires this specific header name.
            "chatgpt-account-id": account_id,
            # Opt-in to the experimental Responses API response format.
            "OpenAI-Beta": _BETA_HEADER,
            # Per-request session UUID for end-to-end request tracing.
            # Using a fresh UUID per call avoids accidental session replay.
            "session_id": str(uuid.uuid4()),
            # Authorization header is injected last so it's easier to audit
            # in code review that we never log it accidentally.
            "Authorization": f"Bearer {access_token}",
            **self.custom_headers,
        }

        return headers

    def _get_streaming_timeout(self) -> httpx.Timeout:
        """Build an httpx.Timeout appropriate for SSE streaming.

        - connect: bounded (default 30 s) — a slow handshake signals infrastructure issues
        - read: unlimited by default — SSE streams can be arbitrarily long-lived
        - write: standard timeout — sending the request body should be fast
        - pool: standard timeout — acquiring a connection from the pool
        """
        return httpx.Timeout(
            connect=self._streaming_connect_timeout,
            read=self._streaming_read_timeout,  # None = no read timeout for SSE
            write=float(self.timeout),
            pool=float(self.timeout),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def stream_responses(
        self,
        request: dict[str, Any],
        request_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a Responses API request and yield raw SSE lines.

        The Responses API only supports streaming (``stream=True`` is
        mandatory).  The caller is responsible for converting the SSE events
        into Claude API format (that's Task 6 — responses_converter.py).
        This method just makes the HTTP call and returns raw lines.

        Args:
            request: Fully-formed Responses API request dict.  Must contain at
                     minimum ``model``, ``instructions``, ``input``, and
                     ``stream=True``.  The caller (responses_converter) is
                     responsible for populating these fields.
            request_id: Optional correlation ID for logging.  Not used for
                        cancellation here (the SSE wrapper handles that).

        Yields:
            Raw SSE lines from the upstream server (e.g. ``data: {...}``).
            Trailing newlines are stripped; blank lines are skipped.
            A final ``data: [DONE]`` sentinel is yielded on clean completion.

        Raises:
            HTTPException: On HTTP-layer errors (4xx/5xx) or unexpected
                           exceptions.  Streaming-specific errors (timeouts,
                           cancellation) are re-raised as-is so the SSE
                           error wrapper in streaming.py can convert them into
                           graceful error events.
            ValueError: If OAuth is not configured or credentials are missing.
        """
        start_time = time.time()
        endpoint_url = f"{self.base_url}{_RESPONSES_ENDPOINT}"

        # Enforce stream=True — the Responses API rejects stream=False.
        # We set it unconditionally rather than raising so callers don't
        # have to remember this API quirk.
        request = {**request, "stream": True}

        # Build per-request headers (fresh dict, no shared-state risk)
        headers = self._build_request_headers()

        # Log the request — but NEVER log Authorization or chatgpt-account-id values.
        if log_request_metrics():
            # Hash the Bearer token for incident correlation (never log plaintext)
            bearer = headers.get("Authorization", "")
            token_part = bearer.removeprefix("Bearer ")
            tok_hash = _token_hash(token_part) if token_part else "none"
            conversation_logger.debug(
                "RESPONSES API STREAM | Model: %s | Token: ...%s | URL: %s | ReqID: %s",
                request.get("model", "unknown"),
                tok_hash,
                endpoint_url,
                request_id or "n/a",
            )

        # Per-request httpx.AsyncClient (Tier-1 simplicity — no lifetime management).
        # Each streaming call opens its own connection.  Connection reuse is a Tier-2
        # optimisation that can be added later without changing the public API.
        try:
            async with (
                httpx.AsyncClient(timeout=self._get_streaming_timeout()) as http_client,
                http_client.stream(
                    "POST",
                    endpoint_url,
                    json=request,
                    headers=headers,
                ) as response,
            ):
                # Raise immediately on HTTP errors before consuming the body.
                # For 4xx/5xx, the server sends a JSON error body (not SSE),
                # so we can read it synchronously here.
                if response.status_code >= 400:
                    await response.aread()
                    error_detail: Any = response.text
                    with contextlib.suppress(json.JSONDecodeError, ValueError):
                        error_detail = response.json()
                    raise HTTPException(status_code=response.status_code, detail=error_detail)

                # Stream SSE lines to the caller.
                # aiter_lines() handles chunked transfer encoding and
                # gives us one logical line per iteration.
                async for line in response.aiter_lines():
                    if line.strip():
                        yield line

                # Emit the [DONE] sentinel so downstream consumers know the
                # stream completed cleanly (vs. being cut off by an error).
                yield "data: [DONE]"

        except HTTPException:
            # HTTP errors are already formatted; let them propagate as-is.
            raise

        except httpx.HTTPStatusError as e:
            # httpx raises this for non-2xx when raise_for_status() was called.
            # We handle status codes manually above, but guard here just in case.
            try:
                content = e.response.read()
                err: Any = json.loads(content.decode("utf-8")) if content else str(e)
            except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
                err = str(e)
            raise HTTPException(status_code=e.response.status_code, detail=err) from None

        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
            # Timeout errors must propagate as-is so the SSE error wrapper in
            # streaming.py can convert them to graceful SSE error events.
            # Converting to HTTPException here would bypass that wrapper.
            logger.debug(
                "ResponsesAPIClient: timeout during streaming — propagating to SSE wrapper"
            )
            raise

        except (httpx.RequestError, httpx.TransportError) as e:
            # Network-layer errors (connection refused, DNS failure, etc.)
            raise HTTPException(
                status_code=502, detail=f"Upstream network error: {type(e).__name__}: {e}"
            ) from e

        except Exception as e:
            # Truly unexpected — log it so we notice, then wrap in 500.
            logger.error(
                "ResponsesAPIClient: unexpected error: %s: %s",
                type(e).__name__,
                e,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Responses API client error: {e}") from e

        # Log timing only on clean completion (errors log separately above)
        if log_request_metrics():
            duration_ms = (time.time() - start_time) * 1000
            conversation_logger.debug(
                "RESPONSES API STREAM COMPLETE | Duration: %.0fms | ReqID: %s",
                duration_ms,
                request_id or "n/a",
            )

    def classify_openai_error(self, error_detail: Any) -> str:
        """Provide error guidance for ChatGPT Responses API issues.

        Required by the error handling pipeline in endpoints.py which calls
        this method on whatever client object is in the request context.
        """
        error_str = str(error_detail).lower()
        if "unauthorized" in error_str or "401" in error_str:
            return (
                "ChatGPT OAuth token expired or invalid. "
                "Run 'vdm oauth login chatgpt' to re-authenticate."
            )
        if "not supported" in error_str:
            return (
                "Model not supported by ChatGPT Responses API. "
                "Use a ChatGPT-compatible model (e.g., gpt-5.4, gpt-5.5)."
            )
        if "instructions are required" in error_str:
            return (
                "ChatGPT Responses API requires an 'instructions' field. "
                "Ensure a system message is included in the request."
            )
        return f"ChatGPT Responses API error: {error_detail}"
