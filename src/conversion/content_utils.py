from __future__ import annotations

import json
from typing import Any, TypeVar

T = TypeVar("T")


def safe_json_loads(value: str | None, *, default: T) -> T:
    # mypy can't always infer that json.loads() returns T; callers provide a typed default.
    """Best-effort JSON parser.

    Conversion code should not fail hard on malformed tool arguments/results; clients
    may stream partial JSON or produce invalid payloads. Callers provide the fallback
    `default` to keep the mapping semantics stable.
    """

    if not value:
        return default

    try:
        return json.loads(value)  # type: ignore[no-any-return]
    except Exception:
        return default


def extract_openai_text_parts(content: Any) -> list[dict[str, Any]]:
    """Extract OpenAI-style text parts from OpenAI message content.

    Supports:
    - content as string
    - content as list[{type: "text", text: ...}, ...]

    Returns a list of content parts suitable for Anthropic Messages API.
    """

    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    if isinstance(content, list):
        parts: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append({"type": "text", "text": str(part.get("text", ""))})
        return parts

    return []


def extract_anthropic_text(content_blocks: Any) -> str | None:
    """Extract concatenated assistant text from an Anthropic content blocks array."""

    if not isinstance(content_blocks, list):
        return None

    parts: list[str] = []
    for block in content_blocks:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        parts.append(str(block.get("text", "")))

    text = "".join(parts)
    return text or None
