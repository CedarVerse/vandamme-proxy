from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from src.conversion.tool_call_delta import ToolCallIdAllocator, coerce_tool_id, coerce_tool_name
from src.core.safe_ops import JSON_PARSE_EXCEPTIONS

logger = logging.getLogger(__name__)


@dataclass
class _SseEvent:
    name: str
    data: str


class _AnthropicToOpenAIChatCompletionsStreamTranslator:
    """Stateful translator for Anthropic Messages SSE -> OpenAI Chat Completions SSE.

    This keeps the generator logic readable by isolating:
    - SSE line parsing / buffering
    - translation state (role emitted, tool id/name maps)
    - emission helpers

    The goal is *clarity without abstraction leakage*: a tiny state machine that can
    be unit tested via the endpoint-level RESPX tests.
    """

    def __init__(self, *, model: str, completion_id: str) -> None:
        self.model = model
        self.completion_id = completion_id
        self.created = int(time.time())

        self.pending_event: str | None = None
        self.pending_data: str | None = None

        self.tool_id_allocator = ToolCallIdAllocator(id_prefix=f"call-{self.completion_id}")
        self.tool_names_by_index: dict[int, str] = {}
        self.emitted_tool_start: set[int] = set()

        self.emitted_role = False
        self.finished = False

    def _emit_chunk(self, delta: dict[str, Any], *, finish_reason: str | None) -> str:
        chunk = {
            "id": self.completion_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    def emit_role_if_needed(self) -> str:
        if self.emitted_role:
            return ""
        self.emitted_role = True
        return self._emit_chunk({"role": "assistant"}, finish_reason=None)

    def emit_text_delta(self, text: str) -> str:
        return self._emit_chunk({"content": text}, finish_reason=None)

    def _tool_id_for_index(self, index: int) -> str:
        return self.tool_id_allocator.get(index)

    def emit_tool_delta(
        self, index: int, *, name: str | None = None, args_delta: str | None = None
    ) -> str:
        tool_id = self._tool_id_for_index(index)

        fn: dict[str, str] = {}
        if name is not None:
            fn["name"] = name
        if args_delta is not None:
            fn["arguments"] = args_delta

        entry: dict[str, Any] = {"index": index, "id": tool_id, "type": "function"}
        if fn:
            entry["function"] = fn

        return self._emit_chunk({"tool_calls": [entry]}, finish_reason=None)

    def emit_finish(self, finish_reason: str) -> str:
        self.finished = True
        return self._emit_chunk({}, finish_reason=finish_reason)

    @staticmethod
    def finish_reason_from_stop_reason(stop_reason: str | None) -> str:
        if stop_reason == "tool_use":
            return "tool_calls"
        if stop_reason == "max_tokens":
            return "length"
        return "stop"

    @staticmethod
    def parse_sse_block(raw: str) -> tuple[str | None, str | None]:
        event: str | None = None
        data: str | None = None
        for line in raw.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        return event, data

    def ingest_line(self, raw_line: str) -> _SseEvent | None:
        """Ingest a single upstream line and return a complete (event,data) when available."""
        line = raw_line.strip()
        if not line:
            return None

        if line.startswith("data: "):
            line = line[len("data: ") :]

        if line == "[DONE]":
            return _SseEvent(name="__done__", data="")

        event, data = self.parse_sse_block(line)

        # Single-line buffering mode
        if event is None and data is None:
            if line.startswith("event:"):
                self.pending_event = line.split(":", 1)[1].strip()
                return None
            if line.startswith("data:"):
                self.pending_data = line.split(":", 1)[1].strip()
                if self.pending_event is not None:
                    ev = _SseEvent(name=self.pending_event, data=self.pending_data)
                    self.pending_event = None
                    self.pending_data = None
                    return ev
                return None
            return None

        # Full block mode
        if event is not None and data is None:
            self.pending_event = event
            return None
        if event is None and self.pending_event is not None:
            event = self.pending_event

        if event is None or data is None:
            return None

        self.pending_event = None
        return _SseEvent(name=event, data=data)


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

    translator = _AnthropicToOpenAIChatCompletionsStreamTranslator(
        model=model, completion_id=completion_id
    )

    async for raw_line in anthropic_sse_lines:
        ev = translator.ingest_line(raw_line)
        if ev is None:
            continue
        if ev.name == "__done__":
            break

        role_delta = translator.emit_role_if_needed()
        if role_delta:
            yield role_delta

        if ev.name == "content_block_start":
            try:
                payload = json.loads(ev.data)
            except JSON_PARSE_EXCEPTIONS as e:
                # Expected during malformed SSE events - log at DEBUG
                logger.debug(f"SSE content_block_start JSON parse error: {type(e).__name__}: {e}")
                continue
            idx = payload.get("index")
            block = payload.get("content_block") or {}
            if not isinstance(idx, int) or not isinstance(block, dict):
                continue

            if block.get("type") == "tool_use":
                block.get("name")
                tool_id = coerce_tool_id(block.get("id"))
                name_s = coerce_tool_name(block.get("name"))
                if name_s is not None:
                    translator.tool_names_by_index[idx] = name_s
                if tool_id is not None:
                    translator.tool_id_allocator.get(idx, provided_id=tool_id)

                translator.emitted_tool_start.add(idx)
                yield translator.emit_tool_delta(idx, name=translator.tool_names_by_index.get(idx))
            continue

        if ev.name == "content_block_delta":
            try:
                payload = json.loads(ev.data)
            except JSON_PARSE_EXCEPTIONS as e:
                # Expected during malformed SSE events - log at DEBUG
                logger.debug(f"SSE content_block_delta JSON parse error: {type(e).__name__}: {e}")
                continue
            idx = payload.get("index")
            delta = payload.get("delta") or {}
            if not isinstance(idx, int) or not isinstance(delta, dict):
                continue

            delta_type = delta.get("type")
            if delta_type == "text_delta":
                text = delta.get("text")
                if isinstance(text, str) and text:
                    yield translator.emit_text_delta(text)
                continue

            if delta_type == "input_json_delta":
                partial = delta.get("partial_json")
                if not isinstance(partial, str) or partial == "":
                    continue

                if idx not in translator.emitted_tool_start:
                    translator.emitted_tool_start.add(idx)
                    yield translator.emit_tool_delta(
                        idx, name=translator.tool_names_by_index.get(idx)
                    )

                yield translator.emit_tool_delta(idx, args_delta=partial)
                continue

        if ev.name == "message_delta":
            try:
                payload = json.loads(ev.data)
            except JSON_PARSE_EXCEPTIONS as e:
                # Expected during malformed SSE events - log at DEBUG
                logger.debug(f"SSE message_delta JSON parse error: {type(e).__name__}: {e}")
                continue

            stop_reason = (payload.get("delta") or {}).get("stop_reason")
            finish_reason = translator.finish_reason_from_stop_reason(stop_reason)
            if not translator.finished:
                yield translator.emit_finish(finish_reason)
            continue

        if ev.name == "message_stop":
            break

    if not translator.finished:
        yield translator.emit_finish("stop")

    yield "data: [DONE]\n\n"
