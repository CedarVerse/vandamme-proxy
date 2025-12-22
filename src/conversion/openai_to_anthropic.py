from __future__ import annotations

import json
from typing import Any

from src.conversion.content_utils import extract_openai_text_parts, safe_json_loads


def _text_parts_from_openai_content(content: Any) -> list[dict[str, Any]]:
    return extract_openai_text_parts(content)


def _system_text_from_openai_messages(messages: list[dict[str, Any]]) -> str | None:
    system_parts: list[str] = []
    for msg in messages:
        if msg.get("role") != "system":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            system_parts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    system_parts.append(str(part.get("text", "")))

    joined = "\n\n".join([p for p in system_parts if p])
    return joined or None


def _anthropic_tools_from_openai_tools(tools: Any) -> list[dict[str, Any]]:
    if not isinstance(tools, list):
        return []

    anthropic_tools: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            continue
        fn = tool.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            continue

        anthropic_tools.append(
            {
                "name": name,
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )

    return anthropic_tools


def _anthropic_tool_use_blocks_from_openai_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []

    blocks: list[dict[str, Any]] = []
    for tc in tool_calls:
        if not isinstance(tc, dict) or tc.get("type") != "function":
            continue
        fn = tc.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        args = fn.get("arguments")
        if not isinstance(name, str) or not name:
            continue
        input_obj: dict[str, Any] = safe_json_loads(
            args if isinstance(args, str) else None,
            default={},
        )

        blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id") or f"call-{name}",
                "name": name,
                "input": input_obj,
            }
        )

    return blocks


def _anthropic_tool_result_message_from_openai_tool_message(msg: dict[str, Any]) -> dict[str, Any]:
    tool_call_id = msg.get("tool_call_id")
    content = msg.get("content")

    tool_content = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)

    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": tool_content,
            }
        ],
    }


def openai_chat_completions_to_anthropic_messages(
    *,
    openai_request: dict[str, Any],
    resolved_model: str,
) -> dict[str, Any]:
    """Convert an OpenAI Chat Completions request into an Anthropic Messages request.

    Subset implementation:
    - messages (system/user/assistant)
    - tools (OpenAI tools -> Anthropic tools)

    Notes:
    - This intentionally does not try to cover the full OpenAI schema.
    - We keep unknown OpenAI fields out of the Anthropic request.
    """

    out: dict[str, Any] = {
        "model": resolved_model,
        # Anthropic requires max_tokens; use OpenAI max_tokens if present.
        "max_tokens": openai_request.get("max_tokens")
        or openai_request.get("max_completion_tokens"),
        "stream": bool(openai_request.get("stream")),
    }

    if out["max_tokens"] is None:
        # Keep behavior simple: require client to set max_tokens.
        # (Cursor/Continue generally do.)
        raise ValueError("OpenAI request missing max_tokens")

    openai_messages = openai_request.get("messages") or []

    # System
    system_text = _system_text_from_openai_messages(openai_messages)
    if system_text is not None:
        out["system"] = system_text

    # Messages
    messages_out: list[dict[str, Any]] = []
    for msg in openai_messages:
        role = msg.get("role")

        if role in ("user", "assistant"):
            content = msg.get("content")
            tool_calls = msg.get("tool_calls")

            if content is None and tool_calls is not None:
                messages_out.append(
                    {
                        "role": role,
                        "content": _anthropic_tool_use_blocks_from_openai_tool_calls(tool_calls),
                    }
                )
                continue

            messages_out.append({"role": role, "content": _text_parts_from_openai_content(content)})
            continue

        if role == "tool":
            messages_out.append(_anthropic_tool_result_message_from_openai_tool_message(msg))
            continue

        # Ignore other roles in subset implementation.
        continue

    out["messages"] = messages_out

    # Tools
    anthropic_tools = _anthropic_tools_from_openai_tools(openai_request.get("tools"))
    if anthropic_tools:
        out["tools"] = anthropic_tools

    return out
