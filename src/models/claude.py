from typing import Any, Literal

from pydantic import BaseModel


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


class ClaudeTokenCountRequest(BaseModel):
    model: str
    messages: list[ClaudeMessage]
    system: str | list[ClaudeSystemContent] | None = None
    tools: list[ClaudeTool] | None = None
    thinking: ClaudeThinkingConfig | None = None
    tool_choice: dict[str, Any] | None = None
