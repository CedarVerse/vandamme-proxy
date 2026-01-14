"""Test helper utilities for streaming state machine tests.

This module provides reusable helper functions for constructing
malformed or edge-case SSE chunks and validating state machine behavior.
"""

from typing import Any

from src.conversion.openai_stream_to_claude_state_machine import OpenAIToClaudeStreamState


def create_malformed_sse_chunk(
    *,
    tool_index: int = 0,
    tool_id: str | None = None,
    tool_name: str | None = None,
    arguments: str | None = None,
    content: str | None = None,
    finish_reason: str | None = None,
) -> dict[str, Any]:
    """Create an SSE chunk with customizable fields for edge case testing.

    Args:
        tool_index: Index for tool call (can be negative for edge cases)
        tool_id: Tool call ID (or None to omit)
        tool_name: Tool function name (or None to omit)
        arguments: Tool arguments string (or None to omit)
        content: Text content delta (or None to omit)
        finish_reason: Finish reason (or None to omit)

    Returns:
        A chunk dict suitable for ingest_openai_chunk()
    """
    delta: dict[str, Any] = {}
    tool_calls = None

    if content is not None:
        delta["content"] = content

    if tool_id is not None or tool_name is not None or arguments is not None:
        tool_calls = []
        tc_delta: dict[str, Any] = {"index": tool_index}

        if tool_id is not None:
            tc_delta["id"] = tool_id

        if tool_name is not None or arguments is not None:
            function: dict[str, Any] = {}
            if tool_name is not None:
                function["name"] = tool_name
            if arguments is not None:
                function["arguments"] = arguments
            tc_delta["function"] = function

        tool_calls.append(tc_delta)
        delta["tool_calls"] = tool_calls

    choice: dict[str, Any] = {"delta": delta}

    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    else:
        choice["finish_reason"] = None

    return {"choices": [choice]}


def create_tool_call_delta(
    index: int,
    *,
    id: str | None = None,
    name: str | None = None,
    arguments: str | None = None,
) -> dict[str, Any]:
    """Create a tool call delta for inclusion in an SSE chunk.

    Args:
        index: Tool call index
        id: Tool call ID (optional)
        name: Tool function name (optional)
        arguments: Tool arguments (optional)

    Returns:
        A tool_call delta dict
    """
    tc_delta: dict[str, Any] = {"index": index}

    if id is not None:
        tc_delta["id"] = id

    if name is not None or arguments is not None:
        function: dict[str, Any] = {}
        if name is not None:
            function["name"] = name
        if arguments is not None:
            function["arguments"] = arguments
        tc_delta["function"] = function

    return tc_delta


def assert_state_invariants(state: OpenAIToClaudeStreamState) -> None:
    """Assert that state machine invariants hold true.

    Args:
        state: The state to validate

    Raises:
        AssertionError: If any invariant is violated
    """
    # Invariant 1: tool_block_counter equals number of started tools
    started_count = sum(1 for tc in state.current_tool_calls.values() if tc.started)
    assert state.tool_block_counter == started_count, (
        f"tool_block_counter ({state.tool_block_counter}) != started tools ({started_count})"
    )

    # Invariant 2: json_sent implies started
    for idx, tc in state.current_tool_calls.items():
        if tc.json_sent:
            assert tc.started, f"Tool {idx}: json_sent=True but started=False"

    # Invariant 3: output_index is set when started
    for idx, tc in state.current_tool_calls.items():
        if tc.started:
            assert tc.output_index is not None, f"Tool {idx}: started=True but output_index is None"


def simulate_incomplete_stream(
    state: OpenAIToClaudeStreamState,
    *,
    tool_started_without_args: bool = False,
    tool_with_incomplete_json: bool = False,
    tool_without_id_or_name: bool = False,
) -> None:
    """Simulate an incomplete stream to test termination handling.

    Args:
        state: The state to modify
        tool_started_without_args: Tool started but never received arguments
        tool_with_incomplete_json: Tool has incomplete JSON in buffer
        tool_without_id_or_name: Tool exists without proper initialization

    Returns:
        None (modifies state in place)
    """
    if tool_started_without_args:
        # Create a tool that started but never got arguments
        state.current_tool_calls[0].tool_id = "call_incomplete"
        state.current_tool_calls[0].tool_name = "incomplete_tool"
        state.current_tool_calls[0].started = True
        state.current_tool_calls[0].output_index = "1"
        state.tool_block_counter = 1

    if tool_with_incomplete_json:
        # Create a tool with incomplete JSON
        state.current_tool_calls[0].tool_id = "call_incomplete_json"
        state.current_tool_calls[0].tool_name = "incomplete_json_tool"
        state.current_tool_calls[0].started = True
        state.current_tool_calls[0].output_index = "1"
        state.current_tool_calls[0].args_buffer = '{"incomplete":'
        state.current_tool_calls[0].json_sent = False
        state.tool_block_counter = 1

    if tool_without_id_or_name:
        # Create a tool entry without proper initialization
        state.current_tool_calls[0] = type(
            "obj",
            (object,),
            {
                "tool_id": None,
                "tool_name": None,
                "started": False,
                "args_buffer": "",
                "json_sent": False,
                "output_index": None,
            },
        )()
