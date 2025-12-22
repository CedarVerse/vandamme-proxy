from __future__ import annotations

import json
import time
from typing import Any


def anthropic_message_to_openai_chat_completion(*, anthropic: dict[str, Any]) -> dict[str, Any]:
    """Convert an Anthropic Messages API response into an OpenAI chat.completion response.

    Subset implementation:
    - text content -> choices[0].message.content
    - tool_use blocks -> choices[0].message.tool_calls
    - usage mapping best-effort
    """

    message_id = anthropic.get("id") or "chatcmpl-anthropic"
    model = anthropic.get("model") or "unknown"

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in anthropic.get("content", []) or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                }
            )

    message: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(text_parts) if text_parts else None,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    stop_reason = anthropic.get("stop_reason")
    finish_reason = "stop"
    if stop_reason == "tool_use":
        finish_reason = "tool_calls"
    elif stop_reason == "max_tokens":
        finish_reason = "length"

    usage = anthropic.get("usage") or {}
    prompt_tokens = usage.get("input_tokens")
    completion_tokens = usage.get("output_tokens")

    out: dict[str, Any] = {
        "id": message_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }

    if prompt_tokens is not None and completion_tokens is not None:
        out["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    return out
