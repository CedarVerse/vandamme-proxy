from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class OpenAIChatCompletionsRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    stream: bool | None = False

    # The rest of OpenAI's schema is large and evolves quickly.
    # We accept additional fields and forward them to the upstream provider.
    model_config = {"extra": "allow"}
