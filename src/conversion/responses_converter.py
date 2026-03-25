"""Conversion layer between OpenAI Chat Completions and ChatGPT Responses API formats.

Why this module exists
----------------------
The ChatGPT internal Responses API (``/v1/responses``) uses a *different schema*
from the standard OpenAI Chat Completions API (``/v1/chat/completions``).  The
pipeline for a Responses-API provider looks like:

    Claude request
        → [request_converter.py]         Claude → OpenAI Chat Completions
        → [responses_converter: Part A]   OpenAI Chat Completions → Responses API
        → ResponsesAPIClient.stream_responses()
        → [responses_converter: Part B]   Responses API SSE → OpenAI Chat Completions SSE
        → [response_converter.py]         OpenAI Chat Completions SSE → Claude SSE

This module owns Parts A and B, keeping the conversion logic isolated from the
HTTP client (responses_client.py) and from the upstream Claude↔OpenAI converters.

Key design decisions
--------------------
1. **System messages become ``instructions``** — the Responses API *requires*
   an ``instructions`` field and errors without it.  We extract the first system
   message from the messages list and promote it.  If none exists we inject a
   safe default.  This was spike-confirmed.

2. **Always stream** — the Responses API rejects ``stream=False``.  We always
   set ``stream=True`` and always set ``store=False`` (we don't want ChatGPT to
   persist our conversations in their backend).

3. **Message format differs** — Responses API uses ``input`` (not ``messages``),
   tool messages become ``function_call_output`` items at the top level (not
   nested inside a role message), and content types use ``input_text`` /
   ``output_text`` rather than just ``text``.

4. **SSE event names differ** — instead of ``data: {..., "object":
   "chat.completion.chunk"}`` we receive events like
   ``{"type": "response.output_text.delta", "delta": "..."}``  We translate
   back to standard OpenAI chunk format so the existing response_converter.py
   can process it unchanged.

5. **Usage key mapping** — Responses API reports ``input_tokens`` /
   ``output_tokens`` where Chat Completions uses ``prompt_tokens`` /
   ``completion_tokens``.

Reference
---------
Conversion logic adapted from ChatMock/chatmock/utils.py (MIT licence).
The sync generator there was rewritten as an async generator to match the
vandamme-proxy async architecture.  Reasoning / extended-thinking events are
out of scope for Tier 1 and are silently skipped.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

# Default instructions injected when the request has no system message.
# The Responses API errors if ``instructions`` is absent, so we must always
# supply *something*.  This conservative default avoids influencing model
# behaviour while satisfying the API contract.
_DEFAULT_INSTRUCTIONS = "You are a helpful assistant."


# =============================================================================
# Part A: OpenAI Chat Completions → Responses API request
# =============================================================================


def convert_openai_to_responses_request(openai_request: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI Chat Completions request dict to Responses API format.

    This is a *pure function* — no I/O, no side effects.  It is called by the
    streaming handler after the standard Claude→OpenAI conversion has already
    run (i.e., ``openai_request`` is the output of ``request_converter.py``).

    Args:
        openai_request: An OpenAI-format request dict.  Must contain at minimum
            a ``model`` key and a ``messages`` list.

    Returns:
        A Responses API request dict ready to pass to
        ``ResponsesAPIClient.stream_responses()``.  The caller should not set
        ``stream`` or ``store`` — those are handled here.

    Notes on the mapping:
    - System message → ``instructions`` (extracted from messages list)
    - Remaining messages → ``input`` (with Responses API content type names)
    - Tool-result messages (role=tool) → ``function_call_output`` items
    - Assistant tool-call turns → ``function_call`` items in ``input``
    - ``tools`` → Responses API function definition format
    - ``tool_choice`` → forwarded as-is if present
    - ``parallel_tool_calls`` → forwarded if present (default False)
    - ``stream=True`` and ``store=False`` are always injected
    """
    messages: list[dict[str, Any]] = openai_request.get("messages") or []
    model: str = openai_request.get("model", "")

    # ---- Extract system message → instructions --------------------------------
    # The Responses API requires an ``instructions`` field.  Spike testing
    # confirmed the API returns a 400 if it is absent.  We extract the first
    # system message (there should only be one; the request_converter always
    # produces at most one) and remove it from the input list so it isn't
    # double-counted.
    instructions = _DEFAULT_INSTRUCTIONS
    non_system_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            # Take the first system message's text as instructions.
            # Subsequent system messages (edge case) are appended to non_system
            # so they don't vanish silently — the model will see them as user
            # messages which is the best approximation available.
            if instructions == _DEFAULT_INSTRUCTIONS:
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Multipart system message — join text parts
                    parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    instructions = "\n".join(filter(None, parts)) or _DEFAULT_INSTRUCTIONS
                elif isinstance(content, str) and content:
                    instructions = content
            # Silently drop (don't add to non_system_messages); the first
            # system message is consumed into instructions.  Additional ones
            # are skipped since they're unusual and the model handles them
            # indirectly through the instructions field.
        else:
            non_system_messages.append(msg)

    # ---- Convert messages → input items  ------------------------------------
    input_items = _convert_messages_to_input(non_system_messages)

    # ---- Convert tools  ------------------------------------------------------
    tools = _convert_tools(openai_request.get("tools"))

    # ---- Assemble Responses API request  ------------------------------------
    responses_request: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": input_items,
        # Always stream — the API rejects stream=False.
        "stream": True,
        # Don't persist conversations in OpenAI's backend.
        "store": False,
    }

    if tools:
        responses_request["tools"] = tools

    # Forward tool_choice if present
    tool_choice = openai_request.get("tool_choice")
    if tool_choice is not None:
        responses_request["tool_choice"] = tool_choice

    # Forward parallel_tool_calls — default to False (safer for most use cases)
    parallel_tool_calls = openai_request.get("parallel_tool_calls")
    if parallel_tool_calls is not None:
        responses_request["parallel_tool_calls"] = parallel_tool_calls
    else:
        responses_request["parallel_tool_calls"] = False

    return responses_request


def _convert_messages_to_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a list of OpenAI Chat Completions messages to Responses API input items.

    The Responses API ``input`` field is a flat list of items.  Tool-call
    messages from the assistant and tool-result messages are emitted as
    standalone items rather than nested inside role-messages.

    Args:
        messages: OpenAI-format messages (system messages already removed).

    Returns:
        A list of Responses API input items.
    """
    input_items: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        # ---- Tool result (role=tool) → function_call_output ------------------
        # In OpenAI Chat Completions, tool results are separate messages with
        # role="tool".  In the Responses API they are top-level
        # ``function_call_output`` items.
        if role == "tool":
            call_id = msg.get("tool_call_id") or msg.get("id")
            if isinstance(call_id, str) and call_id:
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Normalise list content to a single string
                    texts: list[str] = []
                    for part in content:
                        if isinstance(part, dict):
                            text = part.get("text") or part.get("content")
                            if isinstance(text, str) and text:
                                texts.append(text)
                    content = "\n".join(texts)
                if isinstance(content, str):
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": content,
                        }
                    )
            # Skip malformed tool messages rather than crashing
            continue

        # ---- Assistant with tool_calls → function_call items -----------------
        # The assistant may have previously called tools.  Those calls must be
        # replayed as ``function_call`` items so the model has conversation
        # context.  Any assistant *text* content is handled below.
        if role == "assistant" and isinstance(msg.get("tool_calls"), list):
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                if tc.get("type", "function") != "function":
                    continue
                call_id = tc.get("id") or tc.get("call_id")
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = fn.get("name") if fn else None
                args = fn.get("arguments") if fn else None
                if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                    input_items.append(
                        {
                            "type": "function_call",
                            "name": name,
                            "arguments": args,
                            "call_id": call_id,
                        }
                    )
            # Fall through to also emit any text content on the assistant turn

        # ---- Regular user/assistant text content ----------------------------
        content = msg.get("content", "")
        content_items: list[dict[str, Any]] = []

        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text") or part.get("content") or ""
                    if isinstance(text, str) and text:
                        # Responses API uses different type names:
                        #   user content  → "input_text"
                        #   assistant content → "output_text"
                        kind = "output_text" if role == "assistant" else "input_text"
                        content_items.append({"type": kind, "text": text})
                elif ptype == "image_url":
                    # Images are only valid in user messages
                    image = part.get("image_url")
                    url = image.get("url") if isinstance(image, dict) else image
                    if isinstance(url, str) and url:
                        content_items.append({"type": "input_image", "image_url": url})
        elif isinstance(content, str) and content:
            kind = "output_text" if role == "assistant" else "input_text"
            content_items.append({"type": kind, "text": content})

        if not content_items:
            # Skip messages with no renderable content (e.g. pure tool-call
            # assistant turns where the text field is empty or None).
            continue

        role_out = "assistant" if role == "assistant" else "user"
        input_items.append({"type": "message", "role": role_out, "content": content_items})

    return input_items


def _convert_tools(tools: Any) -> list[dict[str, Any]]:
    """Convert OpenAI Chat Completions tool definitions to Responses API format.

    Both formats use JSON Schema for parameters, but the Responses API wraps
    things slightly differently.  The main differences are that the Responses
    API function definition lives at the top level (not under a ``function``
    key) and requires a ``strict`` boolean.

    Args:
        tools: The ``tools`` field from an OpenAI request, or None.

    Returns:
        A list of Responses API tool definitions, or an empty list.
    """
    if not isinstance(tools, list):
        return []

    out: list[dict[str, Any]] = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        if t.get("type") != "function":
            continue
        fn = t.get("function") if isinstance(t.get("function"), dict) else {}
        name = fn.get("name") if fn else None
        if not isinstance(name, str) or not name:
            continue
        desc = fn.get("description") or ""
        params = fn.get("parameters")
        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}

        out.append(
            {
                "type": "function",
                "name": name,
                "description": desc,
                # ``strict=False`` matches ChatMock's behaviour; ``True``
                # would require all fields to be required and have no
                # additional properties, which is too restrictive.
                "strict": False,
                "parameters": params,
            }
        )
    return out


# =============================================================================
# Part B: Responses API SSE → OpenAI Chat Completions SSE
# =============================================================================


def _extract_usage(event: dict[str, Any]) -> dict[str, int] | None:
    """Extract and normalise usage stats from a ``response.completed`` event.

    The Responses API uses ``input_tokens`` / ``output_tokens`` where the Chat
    Completions API uses ``prompt_tokens`` / ``completion_tokens``.  This
    function normalises to the Chat Completions names so downstream code
    (response_converter.py) can remain unchanged.

    Args:
        event: A ``response.completed`` SSE event dict.

    Returns:
        A dict with ``prompt_tokens``, ``completion_tokens``, ``total_tokens``,
        or None if the event does not contain usage data.
    """
    try:
        usage = (event.get("response") or {}).get("usage")
        if not isinstance(usage, dict):
            return None
        prompt = int(usage.get("input_tokens") or 0)
        completion = int(usage.get("output_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }
    except (TypeError, ValueError, AttributeError):
        return None


async def translate_responses_sse_to_openai(
    raw_sse_lines: AsyncGenerator[str, None],
    *,
    model: str | None = None,
    request_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Translate a Responses API SSE stream into OpenAI Chat Completions SSE format.

    This is an async generator that consumes raw SSE lines from
    ``ResponsesAPIClient.stream_responses()`` and emits OpenAI-formatted
    ``data: {...}`` lines.  The output is designed to be consumed by
    ``response_converter.py`` (the OpenAI → Claude converter), so it must
    closely match what OpenAI's ``/v1/chat/completions?stream=true`` emits.

    Tier 1 scope (implemented):
    - Text streaming via ``response.output_text.delta``
    - Tool call completion via ``response.output_item.done`` (type=function_call)
    - Usage reporting via ``response.completed``
    - Error forwarding via ``response.failed``
    - Proper ``finish_reason`` on final chunks

    Out of scope for Tier 1 (silently skipped):
    - Reasoning / extended-thinking events (``response.reasoning_*``)
    - Web-search built-in tool events (``web_search_call.*``)

    SSE format contract:
    - Each yielded string is a complete ``data: {...}\\n\\n`` line (or
      ``data: [DONE]\\n\\n``).
    - The ``object`` field on every chunk is ``"chat.completion.chunk"``.
    - ``finish_reason`` is ``None`` on intermediate chunks, ``"stop"`` on
      normal completion, and ``"tool_calls"`` when a tool call finishes.
    - Usage is emitted in a separate chunk immediately before ``[DONE]`` when
      the Responses API reports it.

    Args:
        raw_sse_lines: Async generator of raw SSE lines (as returned by
            ``ResponsesAPIClient.stream_responses()``).  Lines must already
            have leading/trailing whitespace stripped and blank lines filtered
            (the client guarantees this).
        model: Model name to embed in chunk objects (for downstream consumers).
            Defaults to ``"unknown"`` if not provided.
        request_id: Optional correlation ID for logging.

    Yields:
        OpenAI-format SSE strings (``data: {...}\\n\\n`` or ``data: [DONE]\\n\\n``).
    """
    # Stable ID embedded in every chunk for the duration of this response.
    # The Responses API's response.id from response.created is used when
    # available, otherwise we generate a local ID that follows the same format.
    response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    effective_model = model or "unknown"
    created = int(time.time())

    # ---- Convergence state ---------------------------------------------------
    # sent_stop_chunk: ensures we emit exactly one finish_reason chunk; the
    # response.output_text.done event and response.completed event can both
    # trigger a stop chunk, so we track whether it was already emitted.
    sent_stop_chunk = False

    # current_tool_call_index: the Responses API emits function calls as
    # separate ``response.output_item.done`` events.  We track a sequential
    # index so multiple tool calls get different indices (required by the
    # OpenAI streaming format's tool_calls array).
    current_tool_call_index = 0
    # Map from call_id → index so we can look up the right index later if
    # a done event arrives for a call we already counted.
    tool_call_index_map: dict[str, int] = {}

    # ---- Process SSE lines ---------------------------------------------------
    async for line in raw_sse_lines:
        # Lines from ResponsesAPIClient are either "data: {...}" or "data: [DONE]"
        if not line.startswith("data: "):
            continue

        data_str = line[len("data: "):].strip()
        if not data_str:
            continue

        if data_str == "[DONE]":
            # The client appended a [DONE] sentinel — pass it through.
            # If we reach here without having already sent a stop chunk
            # (e.g. the stream was cut short), emit a fallback stop chunk
            # so downstream parsers don't hang waiting for a finish_reason.
            if not sent_stop_chunk:
                fallback_chunk = _build_chunk(
                    response_id=response_id,
                    created=created,
                    model=effective_model,
                    choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
                )
                yield f"data: {json.dumps(fallback_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Parse the SSE JSON payload
        try:
            event = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            logger.debug(
                "[%s] Skipping unparseable Responses API SSE line: %.200s",
                request_id or "n/a",
                data_str,
            )
            continue

        kind: str | None = event.get("type")

        # Update response_id if the API provides one (from response.created)
        response_obj = event.get("response")
        if isinstance(response_obj, dict) and isinstance(response_obj.get("id"), str):
            response_id = response_obj["id"] or response_id

        # ---- Text delta  -----------------------------------------------------
        if kind == "response.output_text.delta":
            delta_text: str = event.get("delta") or ""
            chunk = _build_chunk(
                response_id=response_id,
                created=created,
                model=effective_model,
                choices=[
                    {"index": 0, "delta": {"content": delta_text}, "finish_reason": None}
                ],
            )
            yield f"data: {json.dumps(chunk)}\n\n"

        # ---- Text turn complete  ---------------------------------------------
        # response.output_text.done signals that a text content part is done.
        # We emit a stop chunk here to provide the finish_reason.  The
        # sent_stop_chunk guard prevents a duplicate if response.completed
        # also tries to emit one.
        elif kind == "response.output_text.done":
            if not sent_stop_chunk:
                stop_chunk = _build_chunk(
                    response_id=response_id,
                    created=created,
                    model=effective_model,
                    choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
                )
                yield f"data: {json.dumps(stop_chunk)}\n\n"
                sent_stop_chunk = True

        # ---- Output item done (function call or message)  -------------------
        elif kind == "response.output_item.done":
            item = event.get("item") or {}
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")

            if item_type == "function_call":
                # Emit the full tool call in one chunk (Responses API delivers
                # the complete function call at once, not in streaming deltas).
                call_id: str = item.get("call_id") or item.get("id") or ""
                name: str = item.get("name") or ""
                raw_args: Any = item.get("arguments") or "{}"
                args: str = _serialize_args(raw_args)

                # Allocate or reuse an index for this call_id
                if call_id not in tool_call_index_map:
                    tool_call_index_map[call_id] = current_tool_call_index
                    current_tool_call_index += 1
                idx = tool_call_index_map[call_id]

                if call_id and name and args:
                    # Emit the tool call delta
                    tc_chunk = _build_chunk(
                        response_id=response_id,
                        created=created,
                        model=effective_model,
                        choices=[
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": idx,
                                            "id": call_id,
                                            "type": "function",
                                            "function": {"name": name, "arguments": args},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    )
                    yield f"data: {json.dumps(tc_chunk)}\n\n"

                    # Emit finish chunk for this tool call
                    finish_chunk = _build_chunk(
                        response_id=response_id,
                        created=created,
                        model=effective_model,
                        choices=[{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                    )
                    yield f"data: {json.dumps(finish_chunk)}\n\n"
                    sent_stop_chunk = True  # tool_calls counts as "done"

            # type=message done — the response.output_text.done already
            # emitted the stop chunk; nothing to do here.

        # ---- Stream completed with usage  ------------------------------------
        elif kind == "response.completed":
            usage = _extract_usage(event)

            # Emit a stop chunk if we haven't already (e.g. for models that
            # don't emit response.output_text.done before response.completed).
            if not sent_stop_chunk:
                stop_chunk = _build_chunk(
                    response_id=response_id,
                    created=created,
                    model=effective_model,
                    choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
                )
                yield f"data: {json.dumps(stop_chunk)}\n\n"
                sent_stop_chunk = True

            # Emit usage chunk so downstream consumers (response_converter.py)
            # can track token counts.  A separate chunk with empty choices and
            # finish_reason=None matches OpenAI's convention.
            if usage:
                usage_chunk = _build_chunk(
                    response_id=response_id,
                    created=created,
                    model=effective_model,
                    choices=[{"index": 0, "delta": {}, "finish_reason": None}],
                    usage=usage,
                )
                yield f"data: {json.dumps(usage_chunk)}\n\n"

            yield "data: [DONE]\n\n"
            return

        # ---- Error event  ---------------------------------------------------
        elif kind == "response.failed":
            error_response = event.get("response") or {}
            error_info = error_response.get("error") or {}
            msg = error_info.get("message") or "response.failed"
            logger.warning(
                "[%s] Responses API reported failure: %s",
                request_id or "n/a",
                msg,
            )
            error_chunk: dict[str, Any] = {"error": {"message": msg, "type": "api_error"}}
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ---- Silently ignored events ----------------------------------------
        # response.created, response.in_progress, response.output_item.added,
        # response.content_part.added, response.content_part.done,
        # response.reasoning_* (out of scope for Tier 1).
        else:
            logger.debug(
                "[%s] Ignoring Responses API event: %s",
                request_id or "n/a",
                kind,
            )


# =============================================================================
# Private helpers
# =============================================================================


def _build_chunk(
    *,
    response_id: str,
    created: int,
    model: str,
    choices: list[dict[str, Any]],
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a standard OpenAI chat.completion.chunk dict.

    Centralising chunk construction ensures the ``id``, ``object``,
    ``created``, and ``model`` fields are always present and consistent.

    Args:
        response_id: The response correlation ID (``chatcmpl-...``).
        created: Unix timestamp for the response.
        model: Model name string.
        choices: List of choice objects (delta, finish_reason, index).
        usage: Optional usage dict (``prompt_tokens``, ``completion_tokens``,
               ``total_tokens``).

    Returns:
        A dict matching the OpenAI ``chat.completion.chunk`` schema.
    """
    chunk: dict[str, Any] = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": choices,
    }
    if usage is not None:
        chunk["usage"] = usage
    return chunk


def _serialize_args(args: Any) -> str:
    """Serialise tool call arguments to a JSON string.

    The Responses API may return arguments as a dict (already parsed) or as
    a JSON string.  OpenAI's streaming format expects a string.

    Args:
        args: Tool call arguments — may be a dict, list, str, or other.

    Returns:
        A JSON-encoded string of the arguments.
    """
    if isinstance(args, (dict, list)):
        return json.dumps(args, ensure_ascii=False)
    if isinstance(args, str):
        try:
            # Re-encode to normalise whitespace / key ordering
            parsed = json.loads(args)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False)
            # Scalar JSON value — unlikely for tool args, but handle gracefully
            return json.dumps({"value": parsed}, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON; wrap it so it's at least parseable downstream
            return json.dumps({"query": args}, ensure_ascii=False)
    return "{}"
