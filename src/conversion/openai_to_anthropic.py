from __future__ import annotations

import json
from typing import Any


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

    system_parts: list[str] = []
    messages_out: list[dict[str, Any]] = []

    for msg in openai_request.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
            elif isinstance(content, list):
                # Best-effort: join text parts.
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        system_parts.append(str(part.get("text", "")))
            continue

        if role in ("user", "assistant"):
            if content is None:
                # tool_calls messages are possible; ignore here (subset).
                messages_out.append({"role": role, "content": []})
                continue
            if isinstance(content, str):
                messages_out.append({"role": role, "content": [{"type": "text", "text": content}]})
            elif isinstance(content, list):
                # Already content parts; pass through text parts only.
                parts: list[dict[str, Any]] = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append({"type": "text", "text": str(part.get("text", ""))})
                messages_out.append({"role": role, "content": parts})
            continue

        if role == "tool":
            # OpenAI tool result message -> Anthropic tool_result content block.
            tool_call_id = msg.get("tool_call_id")
            if isinstance(content, str):
                tool_content = content
            else:
                tool_content = json.dumps(content, ensure_ascii=False)
            messages_out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": tool_content,
                        }
                    ],
                }
            )
            continue

    if system_parts:
        out["system"] = "\n\n".join([p for p in system_parts if p])

    out["messages"] = messages_out

    # Tools
    tools = openai_request.get("tools")
    if isinstance(tools, list):
        anthropic_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict) or tool.get("type") != "function":
                continue
            fn = tool.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            anthropic_tools.append(
                {
                    "name": name,
                    "description": fn.get("description") or "",
                    "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        if anthropic_tools:
            out["tools"] = anthropic_tools

    return out
