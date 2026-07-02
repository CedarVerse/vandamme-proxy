from typing import Any, Literal

from pydantic import BaseModel, model_validator


class ClaudeContentBlockText(BaseModel):
    type: Literal["text"]
    text: str


class ClaudeContentBlockImage(BaseModel):
    type: Literal["image"]
    source: dict[str, Any]


class ClaudeContentBlockToolUse(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ClaudeContentBlockToolResult(BaseModel):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str | list[dict[str, Any]] | dict[str, Any]


class ClaudeContentBlockThinking(BaseModel):
    """Extended-thinking (reasoning) block sent by Claude Code when thinking is enabled.

    Claude Code includes these in assistant messages so the model's chain-of-thought
    can be replayed on subsequent turns. The proxy must accept them to avoid silently
    dropping reasoning context when routing to Anthropic-compatible backends.
    """

    type: Literal["thinking"]
    thinking: str


class ClaudeSystemContent(BaseModel):
    type: Literal["text"]
    text: str


class ClaudeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: (
        str
        | list[
            ClaudeContentBlockText
            | ClaudeContentBlockImage
            | ClaudeContentBlockToolUse
            | ClaudeContentBlockToolResult
            | ClaudeContentBlockThinking
        ]
    )


class ClaudeTool(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any]


class ClaudeThinkingConfig(BaseModel):
    enabled: bool = True


class ClaudeMessagesRequest(BaseModel):
    model: str
    max_tokens: int
    messages: list[ClaudeMessage]
    system: str | list[ClaudeSystemContent] | None = None
    stop_sequences: list[str] | None = None
    stream: bool | None = False
    temperature: float | None = 1.0
    top_p: float | None = None
    top_k: int | None = None
    metadata: dict[str, Any] | None = None
    tools: list[ClaudeTool] | None = None
    tool_choice: dict[str, Any] | None = None
    thinking: ClaudeThinkingConfig | None = None

    @model_validator(mode="before")
    @classmethod
    def promote_system_role_messages(cls, data: Any) -> Any:
        return _promote_system_role_messages(data)


class ClaudeTokenCountRequest(BaseModel):
    model: str
    messages: list[ClaudeMessage]
    system: str | list[ClaudeSystemContent] | None = None
    tools: list[ClaudeTool] | None = None
    thinking: ClaudeThinkingConfig | None = None
    tool_choice: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def promote_system_role_messages(cls, data: Any) -> Any:
        return _promote_system_role_messages(data)


def _promote_system_role_messages(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    messages = data.get("messages")
    if not isinstance(messages, list):
        return data

    system_parts: list[str] = []
    normalized_messages: list[Any] = []
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            system_parts.append(_system_text_from_content(message.get("content")))
        else:
            normalized_messages.append(message)

    if not system_parts:
        return data

    return {
        **data,
        "system": _merge_system_content(data.get("system"), system_parts),
        "messages": normalized_messages,
    }


def _system_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def _merge_system_content(existing: Any, promoted_parts: list[str]) -> str:
    parts: list[str] = []
    if isinstance(existing, str):
        parts.append(existing)
    elif isinstance(existing, list):
        parts.append(_system_text_from_content(existing))
    parts.extend(part for part in promoted_parts if part)
    return "\n\n".join(part for part in parts if part)
