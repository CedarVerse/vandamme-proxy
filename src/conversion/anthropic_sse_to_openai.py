from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator


def _parse_sse_event(raw: str) -> tuple[str | None, str | None]:
    """Parse a single SSE event payload into (event, data).

    Expects a single event block containing lines like:
      event: message_start
      data: {...}

    Returns (None, None) if not parseable.
    """
    event: str | None = None
    data: str | None = None

    for line in raw.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()

    return event, data


async def anthropic_sse_to_openai_chat_completions_sse(
    *,
    anthropic_sse_lines: AsyncGenerator[str, None],
    model: str,
    completion_id: str,
) -> AsyncGenerator[str, None]:
    """Translate Anthropic Messages SSE events into OpenAI Chat Completions SSE.

    Subset mapping:
    - text deltas -> choices[].delta.content
    - message_delta stop_reason -> finish_reason

    Emits OpenAI-style SSE lines:
      data: {"object":"chat.completion.chunk", ...}\n\n
    and terminates with:
      data: [DONE]\n\n
    Notes:
    - This expects upstream lines to contain the full SSE event lines (`event:` + `data:`).
    - In this codebase `AnthropicClient.create_chat_completion_stream` yields lines prefixed
      with `data: ` and without SSE newlines. To make translation robust, we treat the
      payload after `data:` as either:
        (a) a full SSE block (with embedded newlines), or
        (b) a single SSE line (e.g. `event: ...` or `data: {...}`), in which case we buffer
            until we have both event and data.
    """

    created = int(time.time())

    pending_event: str | None = None

    async for raw_line in anthropic_sse_lines:
        line = raw_line.strip()
        if not line:
            continue

        # Handle wrappers that yield `data: ...` for each upstream line.
        if line.startswith("data: "):
            line = line[len("data: ") :]

        # Anthropic stream may include [DONE] sentinel from our passthrough client.
        if line == "[DONE]":
            break

        # Case (a): the payload is a full SSE block containing both event + data.
        event, data = _parse_sse_event(line)

        # Case (b): payload is a single SSE line; buffer until we have both.
        if event is None and data is None:
            if line.startswith("event:"):
                pending_event = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                line.split(":", 1)[1].strip()
                continue
            continue

        # If we only received an event name, buffer it and wait for a data line.
        if event is not None and data is None:
            pending_event = event
            continue

        # If we only received data, use buffered event if available.
        if event is None and pending_event is not None:
            event = pending_event

        # If we received a data line without an event line, ignore.
        if event is None or data is None:
            continue

        # Clear buffers after successful assembly.
        pending_event = None

        if event == "content_block_delta":
            try:
                payload = json.loads(data)
            except Exception:
                continue
            delta = payload.get("delta") or {}
            if delta.get("type") != "text_delta":
                continue
            text = delta.get("text")
            if not text:
                continue

            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": text},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        elif event == "message_delta":
            # Emit a terminating chunk with finish_reason.
            try:
                payload = json.loads(data)
            except Exception:
                continue

            stop_reason = (payload.get("delta") or {}).get("stop_reason")
            finish_reason = "stop"
            if stop_reason == "tool_use":
                finish_reason = "tool_calls"
            elif stop_reason == "max_tokens":
                finish_reason = "length"

            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": finish_reason,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        elif event == "message_stop":
            break

    yield "data: [DONE]\n\n"
