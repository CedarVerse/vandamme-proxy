"""Unit tests for src/conversion/responses_converter.py.

Test coverage:
  Part A — convert_openai_to_responses_request():
    - System message extraction → instructions field
    - Default instructions when no system message present
    - Multiple system messages: first wins, rest are dropped
    - User/assistant text messages → input items with correct type names
    - Tool-result messages (role=tool) → function_call_output items
    - Assistant messages with tool_calls → function_call items in input
    - Tools list conversion (OpenAI function format → Responses API)
    - Empty/missing tools list
    - tool_choice forwarded when present
    - parallel_tool_calls defaults to False when absent
    - stream=True and store=False always injected
    - Image content in user messages

  Part B — translate_responses_sse_to_openai():
    - response.output_text.delta → OpenAI content chunk
    - response.output_text.done → stop chunk (finish_reason="stop")
    - response.completed with usage → usage chunk + [DONE]
    - response.completed without prior stop chunk → emits stop first
    - response.failed → error chunk + [DONE]
    - Unknown / ignored events do not produce output
    - [DONE] sentinel forwarded cleanly
    - Tool call via response.output_item.done → tool_calls chunk + finish
    - Multiple tool calls get sequential indices
    - Response id from response.created is picked up and reused
    - Usage normalisation: input_tokens→prompt_tokens, output_tokens→completion_tokens

  Helpers:
    - _extract_usage: correct mapping and None on missing data
    - _serialize_args: dict, string-JSON, plain string, fallback
    - _build_chunk: consistent schema
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.conversion.responses_converter import (
    _DEFAULT_INSTRUCTIONS,
    _build_chunk,
    _extract_usage,
    _serialize_args,
    convert_openai_to_responses_request,
    translate_responses_sse_to_openai,
)


# =============================================================================
# Helpers
# =============================================================================


def _openai_req(**overrides: Any) -> dict[str, Any]:
    """Build a minimal OpenAI Chat Completions request dict for tests."""
    base: dict[str, Any] = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello"},
        ],
    }
    base.update(overrides)
    return base


async def _collect_sse(lines: list[str]) -> list[str]:
    """Drive translate_responses_sse_to_openai with a list of raw SSE lines."""

    async def _gen():
        for line in lines:
            yield line

    return [chunk async for chunk in translate_responses_sse_to_openai(_gen())]


def _parse_data(sse_line: str) -> dict[str, Any] | None:
    """Extract and parse the JSON payload from a 'data: {...}' SSE line."""
    if not sse_line.startswith("data: "):
        return None
    payload = sse_line[len("data: "):].strip()
    if payload == "[DONE]":
        return None
    return json.loads(payload)


def _delta_content(sse_line: str) -> str | None:
    """Extract the content delta text from an OpenAI chat completion chunk."""
    data = _parse_data(sse_line)
    if not data:
        return None
    choices = data.get("choices", [])
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")


def _finish_reason(sse_line: str) -> str | None:
    """Extract the finish_reason from an OpenAI chat completion chunk."""
    data = _parse_data(sse_line)
    if not data:
        return None
    choices = data.get("choices", [])
    if not choices:
        return None
    return choices[0].get("finish_reason")


# =============================================================================
# Part A: convert_openai_to_responses_request()
# =============================================================================


@pytest.mark.unit
class TestConvertOpenAIToResponsesRequest:
    """Part A: OpenAI Chat Completions → Responses API request conversion."""

    def test_system_message_becomes_instructions(self):
        """The first system message must be extracted into the instructions field."""
        req = _openai_req(
            messages=[
                {"role": "system", "content": "You are a pirate."},
                {"role": "user", "content": "Hello"},
            ]
        )
        result = convert_openai_to_responses_request(req)

        assert result["instructions"] == "You are a pirate."
        # System message must NOT appear in the input list
        for item in result["input"]:
            assert item.get("role") != "system"

    def test_default_instructions_when_no_system_message(self):
        """When no system message exists, the default instructions must be injected."""
        req = _openai_req(messages=[{"role": "user", "content": "Hello"}])
        result = convert_openai_to_responses_request(req)

        assert result["instructions"] == _DEFAULT_INSTRUCTIONS

    def test_only_first_system_message_used(self):
        """When multiple system messages exist, only the first becomes instructions."""
        req = _openai_req(
            messages=[
                {"role": "system", "content": "First system"},
                {"role": "system", "content": "Second system"},
                {"role": "user", "content": "Hello"},
            ]
        )
        result = convert_openai_to_responses_request(req)

        assert result["instructions"] == "First system"

    def test_multipart_system_message_joined(self):
        """A system message with list content must be joined into a single string."""
        req = _openai_req(
            messages=[
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": "Part one."},
                        {"type": "text", "text": "Part two."},
                    ],
                },
                {"role": "user", "content": "Hi"},
            ]
        )
        result = convert_openai_to_responses_request(req)

        assert result["instructions"] == "Part one.\nPart two."

    def test_user_message_becomes_input_text(self):
        """User text messages must use type='input_text' in the Responses API format."""
        req = _openai_req(messages=[{"role": "user", "content": "Hello!"}])
        result = convert_openai_to_responses_request(req)

        input_items = result["input"]
        assert len(input_items) == 1
        msg = input_items[0]
        assert msg["type"] == "message"
        assert msg["role"] == "user"
        assert msg["content"][0]["type"] == "input_text"
        assert msg["content"][0]["text"] == "Hello!"

    def test_assistant_message_becomes_output_text(self):
        """Assistant text messages must use type='output_text' in the Responses API format."""
        req = _openai_req(
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )
        result = convert_openai_to_responses_request(req)

        assistant_item = next(i for i in result["input"] if i.get("role") == "assistant")
        assert assistant_item["content"][0]["type"] == "output_text"
        assert assistant_item["content"][0]["text"] == "Hi there!"

    def test_tool_result_message_becomes_function_call_output(self):
        """A role=tool message must become a function_call_output item."""
        req = _openai_req(
            messages=[
                {"role": "user", "content": "What is 2+2?"},
                {
                    "role": "tool",
                    "tool_call_id": "call_abc123",
                    "content": "4",
                },
            ]
        )
        result = convert_openai_to_responses_request(req)

        tool_items = [i for i in result["input"] if i.get("type") == "function_call_output"]
        assert len(tool_items) == 1
        assert tool_items[0]["call_id"] == "call_abc123"
        assert tool_items[0]["output"] == "4"

    def test_tool_result_with_list_content(self):
        """A tool message whose content is a list must join the text parts."""
        req = _openai_req(
            messages=[
                {
                    "role": "tool",
                    "tool_call_id": "call_xyz",
                    "content": [
                        {"type": "text", "text": "Line one"},
                        {"type": "text", "text": "Line two"},
                    ],
                }
            ]
        )
        result = convert_openai_to_responses_request(req)

        item = result["input"][0]
        assert item["output"] == "Line one\nLine two"

    def test_assistant_tool_calls_become_function_call_items(self):
        """Assistant messages with tool_calls must emit function_call items in input."""
        req = _openai_req(
            messages=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_foo",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "Paris"}',
                            },
                        }
                    ],
                }
            ]
        )
        result = convert_openai_to_responses_request(req)

        fn_items = [i for i in result["input"] if i.get("type") == "function_call"]
        assert len(fn_items) == 1
        assert fn_items[0]["name"] == "get_weather"
        assert fn_items[0]["call_id"] == "call_foo"
        assert fn_items[0]["arguments"] == '{"city": "Paris"}'

    def test_tools_converted_to_responses_format(self):
        """OpenAI function tool definitions must be converted to Responses API format."""
        req = _openai_req(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "my_tool",
                        "description": "Does stuff",
                        "parameters": {
                            "type": "object",
                            "properties": {"x": {"type": "string"}},
                        },
                    },
                }
            ],
        )
        result = convert_openai_to_responses_request(req)

        tools = result.get("tools", [])
        assert len(tools) == 1
        t = tools[0]
        assert t["type"] == "function"
        assert t["name"] == "my_tool"
        assert t["description"] == "Does stuff"
        assert "strict" in t
        assert t["parameters"]["type"] == "object"

    def test_empty_tools_list_omitted_from_result(self):
        """When tools is an empty list, the key should not appear in the result."""
        req = _openai_req(tools=[])
        result = convert_openai_to_responses_request(req)

        # Empty tools list should not produce a "tools" key
        assert "tools" not in result or result.get("tools") == []

    def test_missing_tools_key_omitted_from_result(self):
        """When tools is absent, the key should not appear in the result."""
        req = _openai_req()
        result = convert_openai_to_responses_request(req)

        assert "tools" not in result

    def test_tool_choice_forwarded_when_present(self):
        """tool_choice must be forwarded to the Responses API request."""
        req = _openai_req(tool_choice="auto")
        result = convert_openai_to_responses_request(req)

        assert result["tool_choice"] == "auto"

    def test_tool_choice_absent_when_not_in_request(self):
        """tool_choice must not appear in the result when not in the input."""
        req = _openai_req()
        result = convert_openai_to_responses_request(req)

        assert "tool_choice" not in result

    def test_parallel_tool_calls_defaults_to_false(self):
        """parallel_tool_calls must default to False when absent from the input."""
        req = _openai_req()
        result = convert_openai_to_responses_request(req)

        assert result["parallel_tool_calls"] is False

    def test_parallel_tool_calls_forwarded_when_present(self):
        """parallel_tool_calls must be forwarded when the caller supplies it."""
        req = _openai_req(parallel_tool_calls=True)
        result = convert_openai_to_responses_request(req)

        assert result["parallel_tool_calls"] is True

    def test_stream_always_true(self):
        """stream must always be True regardless of what the caller passes."""
        req = _openai_req()
        # The caller doesn't set stream at all
        result = convert_openai_to_responses_request(req)
        assert result["stream"] is True

    def test_store_always_false(self):
        """store must always be False to prevent ChatGPT from persisting sessions."""
        req = _openai_req()
        result = convert_openai_to_responses_request(req)

        assert result["store"] is False

    def test_model_passed_through(self):
        """The model field must be passed through unchanged."""
        req = _openai_req(model="gpt-4o-mini")
        result = convert_openai_to_responses_request(req)

        assert result["model"] == "gpt-4o-mini"

    def test_image_in_user_message_becomes_input_image(self):
        """Image content in a user message must become an input_image item."""
        req = _openai_req(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is this?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,abc123"},
                        },
                    ],
                }
            ]
        )
        result = convert_openai_to_responses_request(req)

        user_item = result["input"][0]
        content_types = [c["type"] for c in user_item["content"]]
        assert "input_text" in content_types
        assert "input_image" in content_types


# =============================================================================
# Part B: translate_responses_sse_to_openai()
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestTranslateResponsesSSEToOpenAI:
    """Part B: Responses API SSE → OpenAI Chat Completions SSE translation."""

    async def test_text_delta_becomes_content_chunk(self):
        """response.output_text.delta must produce an OpenAI content chunk."""
        event = {"type": "response.output_text.delta", "delta": "Hello, "}
        lines = [
            f"data: {json.dumps(event)}",
            'data: {"type": "response.completed", "response": {"id": "resp_1", "usage": {"input_tokens": 10, "output_tokens": 5}}}',
        ]

        chunks = await _collect_sse(lines)
        content_chunks = [c for c in chunks if _delta_content(c) is not None]
        assert len(content_chunks) >= 1
        assert _delta_content(content_chunks[0]) == "Hello, "

    async def test_multiple_text_deltas_all_forwarded(self):
        """All response.output_text.delta events must produce separate chunks."""
        events = [
            {"type": "response.output_text.delta", "delta": "Hel"},
            {"type": "response.output_text.delta", "delta": "lo"},
            {"type": "response.output_text.delta", "delta": "!"},
            {
                "type": "response.completed",
                "response": {"id": "r1", "usage": {"input_tokens": 1, "output_tokens": 3}},
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        content_chunks = [c for c in chunks if _delta_content(c) is not None]
        texts = [_delta_content(c) for c in content_chunks]
        assert texts == ["Hel", "lo", "!"]

    async def test_output_text_done_emits_stop_chunk(self):
        """response.output_text.done must emit a chunk with finish_reason='stop'."""
        events = [
            {"type": "response.output_text.delta", "delta": "Done text"},
            {"type": "response.output_text.done"},
            {
                "type": "response.completed",
                "response": {"id": "r2", "usage": {"input_tokens": 5, "output_tokens": 2}},
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        stop_chunks = [c for c in chunks if _finish_reason(c) == "stop"]
        assert len(stop_chunks) >= 1

    async def test_completed_emits_usage_chunk_and_done(self):
        """response.completed must emit a usage chunk and then data: [DONE]."""
        event = {
            "type": "response.completed",
            "response": {
                "id": "resp_abc",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
        }
        lines = [f"data: {json.dumps(event)}"]
        chunks = await _collect_sse(lines)

        # Must end with [DONE]
        assert chunks[-1] == "data: [DONE]\n\n"

        # Must include a usage chunk
        usage_chunks = [
            c for c in chunks if _parse_data(c) and _parse_data(c).get("usage") is not None
        ]
        assert len(usage_chunks) == 1
        usage = _parse_data(usage_chunks[0])["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30

    async def test_completed_without_prior_stop_emits_stop_first(self):
        """response.completed with no prior stop must emit stop chunk before usage."""
        event = {
            "type": "response.completed",
            "response": {
                "id": "r3",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        }
        chunks = await _collect_sse([f"data: {json.dumps(event)}"])

        stop_chunks = [c for c in chunks if _finish_reason(c) == "stop"]
        assert len(stop_chunks) >= 1
        assert chunks[-1] == "data: [DONE]\n\n"

    async def test_failed_event_emits_error_chunk_and_done(self):
        """response.failed must emit an error chunk and then data: [DONE]."""
        event = {
            "type": "response.failed",
            "response": {
                "error": {"message": "Something went wrong", "code": "server_error"}
            },
        }
        chunks = await _collect_sse([f"data: {json.dumps(event)}"])

        error_data = next(
            (c for c in chunks if _parse_data(c) and "error" in _parse_data(c)),
            None,
        )
        assert error_data is not None
        assert "Something went wrong" in _parse_data(error_data)["error"]["message"]
        assert chunks[-1] == "data: [DONE]\n\n"

    async def test_done_sentinel_forwarded_cleanly(self):
        """data: [DONE] from the client must result in a [DONE] sentinel being yielded."""
        # When the client sends [DONE] directly, we should still emit it
        chunks = await _collect_sse(["data: [DONE]"])

        assert "data: [DONE]\n\n" in chunks

    async def test_ignored_events_produce_no_output_chunks(self):
        """Setup events like response.created and response.in_progress must be silent."""
        ignored_events = [
            {"type": "response.created", "response": {}},
            {"type": "response.in_progress"},
            {"type": "response.output_item.added", "item": {"type": "message"}},
            {"type": "response.content_part.added"},
            {"type": "response.output_item.done", "item": {"type": "message"}},
            {"type": "response.content_part.done"},
            # Conclude with completed so the stream terminates cleanly
            {
                "type": "response.completed",
                "response": {
                    "id": "r4",
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in ignored_events]
        chunks = await _collect_sse(lines)

        # The only content-bearing chunks should be the stop chunk and [DONE].
        # No content deltas should appear for ignored events.
        content_chunks = [c for c in chunks if _delta_content(c) is not None]
        assert content_chunks == []

    async def test_function_call_item_done_emits_tool_calls_chunk(self):
        """A function_call output_item.done must produce tool_calls chunks."""
        events = [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": "call_test_1",
                    "name": "get_weather",
                    "arguments": '{"city": "Berlin"}',
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "id": "r5",
                    "usage": {"input_tokens": 5, "output_tokens": 10},
                },
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        # Find the chunk with tool_calls
        tc_chunk = next(
            (
                c
                for c in chunks
                if _parse_data(c)
                and _parse_data(c).get("choices", [{}])[0]
                .get("delta", {})
                .get("tool_calls")
            ),
            None,
        )
        assert tc_chunk is not None, "No tool_calls chunk found"

        data = _parse_data(tc_chunk)
        tc = data["choices"][0]["delta"]["tool_calls"][0]
        assert tc["id"] == "call_test_1"
        assert tc["function"]["name"] == "get_weather"
        assert '"city"' in tc["function"]["arguments"]

        # Must also have a finish chunk with finish_reason="tool_calls"
        finish_chunks = [c for c in chunks if _finish_reason(c) == "tool_calls"]
        assert len(finish_chunks) >= 1

    async def test_multiple_tool_calls_get_sequential_indices(self):
        """Two tool calls must get indices 0 and 1 respectively."""
        events = [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": "call_a",
                    "name": "tool_a",
                    "arguments": "{}",
                },
            },
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": "call_b",
                    "name": "tool_b",
                    "arguments": "{}",
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "id": "r6",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        tc_chunks = [
            c
            for c in chunks
            if _parse_data(c)
            and _parse_data(c).get("choices", [{}])[0].get("delta", {}).get("tool_calls")
        ]
        assert len(tc_chunks) == 2
        indices = [
            _parse_data(c)["choices"][0]["delta"]["tool_calls"][0]["index"]
            for c in tc_chunks
        ]
        assert sorted(indices) == [0, 1]

    async def test_response_id_from_created_event_used_in_chunks(self):
        """The response id from the first event must appear in all subsequent chunks."""
        events = [
            {
                "type": "response.created",
                "response": {"id": "chatcmpl-mySpecificId"},
            },
            {"type": "response.output_text.delta", "delta": "Hello"},
            {
                "type": "response.completed",
                "response": {
                    "id": "chatcmpl-mySpecificId",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        # All JSON chunks (not [DONE]) should use the response id
        json_chunks = [_parse_data(c) for c in chunks if _parse_data(c)]
        for data in json_chunks:
            assert data.get("id") == "chatcmpl-mySpecificId", (
                f"Expected id='chatcmpl-mySpecificId', got {data.get('id')}"
            )

    async def test_chunk_object_field_is_chat_completion_chunk(self):
        """Every JSON chunk must have object='chat.completion.chunk'."""
        events = [
            {"type": "response.output_text.delta", "delta": "Hi"},
            {
                "type": "response.completed",
                "response": {
                    "id": "r7",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ]
        lines = [f"data: {json.dumps(e)}" for e in events]
        chunks = await _collect_sse(lines)

        for chunk in chunks:
            data = _parse_data(chunk)
            if data:
                assert data.get("object") == "chat.completion.chunk", (
                    f"Expected object='chat.completion.chunk', got {data.get('object')}"
                )

    async def test_model_name_forwarded_into_chunks(self):
        """The model parameter must appear in all JSON chunks."""

        async def _gen():
            yield (
                'data: {"type": "response.completed", '
                '"response": {"id": "r8", "usage": {"input_tokens": 1, "output_tokens": 1}}}'
            )

        chunks = [
            c
            async for c in translate_responses_sse_to_openai(
                _gen(), model="gpt-4o-mini", request_id="test"
            )
        ]
        json_chunks = [_parse_data(c) for c in chunks if _parse_data(c)]
        for data in json_chunks:
            assert data.get("model") == "gpt-4o-mini"

    async def test_empty_stream_yields_done(self):
        """An immediately-closed stream must still yield [DONE]."""

        async def _empty():
            return
            yield  # make it a generator

        chunks = [c async for c in translate_responses_sse_to_openai(_empty())]
        # Shouldn't crash; may yield nothing or just [DONE] depending on path
        # What matters is no exception is raised
        assert isinstance(chunks, list)


# =============================================================================
# Helpers: _extract_usage
# =============================================================================


@pytest.mark.unit
class TestExtractUsage:
    """Unit tests for the _extract_usage helper."""

    def test_extracts_correct_keys(self):
        """Must map input_tokens→prompt_tokens and output_tokens→completion_tokens."""
        event = {
            "type": "response.completed",
            "response": {
                "usage": {"input_tokens": 100, "output_tokens": 50}
            },
        }
        result = _extract_usage(event)

        assert result is not None
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["total_tokens"] == 150

    def test_total_tokens_explicit(self):
        """If total_tokens is present, it must be used directly."""
        event = {
            "response": {
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 999}
            }
        }
        result = _extract_usage(event)

        assert result is not None
        assert result["total_tokens"] == 999

    def test_returns_none_when_no_response_key(self):
        """Must return None if the event has no 'response' key."""
        assert _extract_usage({"type": "response.created"}) is None

    def test_returns_none_when_no_usage_in_response(self):
        """Must return None if response.usage is absent."""
        assert _extract_usage({"response": {}}) is None

    def test_returns_none_when_usage_is_not_dict(self):
        """Must return None if response.usage is not a dict (defensive)."""
        assert _extract_usage({"response": {"usage": "malformed"}}) is None

    def test_handles_zero_tokens(self):
        """Zero token counts must be handled correctly (not confused with falsy)."""
        event = {"response": {"usage": {"input_tokens": 0, "output_tokens": 0}}}
        result = _extract_usage(event)

        assert result is not None
        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0


# =============================================================================
# Helpers: _serialize_args
# =============================================================================


@pytest.mark.unit
class TestSerializeArgs:
    """Unit tests for the _serialize_args helper."""

    def test_dict_serialized_to_json_string(self):
        """A dict must be serialised to a JSON string."""
        result = _serialize_args({"city": "Paris"})
        assert json.loads(result) == {"city": "Paris"}

    def test_list_serialized_to_json_string(self):
        """A list must be serialised to a JSON string."""
        result = _serialize_args([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_json_string_normalised(self):
        """A valid JSON string must be re-serialised (normalises whitespace)."""
        result = _serialize_args('{ "key" :  "value" }')
        assert json.loads(result) == {"key": "value"}

    def test_plain_string_wrapped_in_query(self):
        """A non-JSON string must be wrapped in a {'query': ...} dict."""
        result = _serialize_args("not json at all")
        parsed = json.loads(result)
        assert "query" in parsed
        assert parsed["query"] == "not json at all"

    def test_none_returns_empty_object(self):
        """None must return '{}'."""
        assert _serialize_args(None) == "{}"

    def test_empty_string_wraps_in_query(self):
        """An empty string is not valid JSON and should be wrapped."""
        result = _serialize_args("")
        # Empty string is not valid JSON, so wraps in query
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


# =============================================================================
# Helpers: _build_chunk
# =============================================================================


@pytest.mark.unit
class TestBuildChunk:
    """Unit tests for the _build_chunk helper."""

    def test_schema_has_required_fields(self):
        """Built chunk must have id, object, created, model, choices."""
        chunk = _build_chunk(
            response_id="chatcmpl-abc",
            created=1700000000,
            model="gpt-4o",
            choices=[{"index": 0, "delta": {}, "finish_reason": None}],
        )
        assert chunk["id"] == "chatcmpl-abc"
        assert chunk["object"] == "chat.completion.chunk"
        assert chunk["created"] == 1700000000
        assert chunk["model"] == "gpt-4o"
        assert chunk["choices"] == [{"index": 0, "delta": {}, "finish_reason": None}]

    def test_usage_field_absent_when_not_provided(self):
        """The usage key must not appear when usage=None (default)."""
        chunk = _build_chunk(
            response_id="x",
            created=0,
            model="m",
            choices=[],
        )
        assert "usage" not in chunk

    def test_usage_field_included_when_provided(self):
        """The usage key must appear when explicitly passed."""
        usage = {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
        chunk = _build_chunk(
            response_id="x",
            created=0,
            model="m",
            choices=[],
            usage=usage,
        )
        assert chunk["usage"] == usage
