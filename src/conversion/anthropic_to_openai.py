from __future__ import annotations

import json
import time
from typing import Any


def _openai_finish_reason_from_anthropic_stop_reason(stop_reason: str | None) -> str:
    if stop_reason == "tool_use":
        return "tool_calls"
    if stop_reason == "max_tokens":
        return "length"
    return "stop"


def _openai_tool_calls_from_anthropic_content(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []

    tool_calls: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue

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

    return tool_calls


def _assistant_text_from_anthropic_content(content: Any) -> str | None:
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        parts.append(str(block.get("text", "")))

    text = "".join(parts)
    return text or None


def _openai_usage_from_anthropic_usage(usage: Any) -> dict[str, int] | None:
    if not isinstance(usage, dict):
        return None

    prompt_tokens = usage.get("input_tokens")
    completion_tokens = usage.get("output_tokens")

    if prompt_tokens is None or completion_tokens is None:
        return None

    return {
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(prompt_tokens) + int(completion_tokens),
    }


def anthropic_message_to_openai_chat_completion(*, anthropic: dict[str, Any]) -> dict[str, Any]:
    """Convert an Anthropic Messages API response into an OpenAI chat.completion response.

    Subset implementation:
    - text content -> choices[0].message.content
    - tool_use blocks -> choices[0].message.tool_calls
    - usage mapping best-effort
    """

    message_id = anthropic.get("id") or "chatcmpl-anthropic"
    model = anthropic.get("model") or "unknown"

    content = anthropic.get("content")
    tool_calls = _openai_tool_calls_from_anthropic_content(content)

    message: dict[str, Any] = {
        "role": "assistant",
        "content": _assistant_text_from_anthropic_content(content),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = _openai_finish_reason_from_anthropic_stop_reason(anthropic.get("stop_reason"))

    out: dict[str, Any] = {
        "id": message_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }

    usage = _openai_usage_from_anthropic_usage(anthropic.get("usage"))
    if usage is not None:
        out["usage"] = usage

    return out
