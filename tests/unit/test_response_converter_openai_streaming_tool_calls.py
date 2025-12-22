import json

import pytest

from src.conversion.response_converter import convert_openai_streaming_to_claude
from src.models.claude import ClaudeMessage, ClaudeMessagesRequest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_convert_openai_streaming_to_claude_buffers_partial_tool_json_until_complete() -> (
    None
):
    # OpenAI SSE stream where tool call arguments arrive in multiple deltas.
    openai_lines = [
        "data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_0",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )
        + "\n",
        "data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "type": "function",
                                    "function": {"arguments": '"2+2"}'},
                                }
                            ]
                        }
                    }
                ]
            }
        )
        + "\n",
        "data: " + json.dumps({"choices": [{"finish_reason": "tool_calls", "delta": {}}]}) + "\n",
        "data: [DONE]\n",
    ]

    async def _gen():
        for line in openai_lines:
            yield line

    original_request = ClaudeMessagesRequest(
        model="openai:gpt-4",
        max_tokens=10,
        messages=[ClaudeMessage(role="user", content="hi")],
    )

    body = "".join(
        [
            chunk
            async for chunk in convert_openai_streaming_to_claude(
                _gen(),
                original_request,
                logger=None,
            )
        ]
    )

    # We should emit a tool_use start and a single input_json_delta once JSON is complete.
    assert "content_block_start" in body
    assert "tool_use" in body
    assert '"name": "calculator"' in body
    assert "input_json_delta" in body
    assert "partial_json" in body
    assert '"stop_reason": "tool_use"' in body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_convert_openai_streaming_to_claude_interleaves_text_and_tool_calls() -> None:
    openai_lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "Working..."}}]}) + "\n",
        "data: "
        + json.dumps(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_0",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression": "2+2"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )
        + "\n",
        "data: " + json.dumps({"choices": [{"finish_reason": "tool_calls", "delta": {}}]}) + "\n",
        "data: [DONE]\n",
    ]

    async def _gen():
        for line in openai_lines:
            yield line

    original_request = ClaudeMessagesRequest(
        model="openai:gpt-4",
        max_tokens=10,
        messages=[ClaudeMessage(role="user", content="hi")],
    )

    body = "".join(
        [
            chunk
            async for chunk in convert_openai_streaming_to_claude(
                _gen(),
                original_request,
                logger=None,
            )
        ]
    )

    # We should preserve text deltas and still emit tool use.
    assert "text_delta" in body
    assert "Working..." in body
    assert "tool_use" in body
