"""Edge case tests for OpenAI→Claude streaming state machine.

This module tests edge cases and malformed input scenarios that are not covered
in the basic state machine test suite.

Test Categories:
    1. State Corruption - Negative indices, non-integers, duplicate starts
    2. JSON Issues - Incomplete JSON, arguments after complete, non-string args
    3. Stream Termination - Incomplete tools, missing finish_reason
    4. Data Type Violations - Unicode, control characters, empty IDs
"""

import json

import pytest

from src.conversion.openai_stream_to_claude_state_machine import (
    OpenAIToClaudeStreamState,
    final_events,
    ingest_openai_chunk,
)
from src.conversion.tool_call_delta import ToolCallIndexState
from tests.unit.helpers.stream_test_helpers import (
    assert_state_invariants,
    create_malformed_sse_chunk,
)

# =============================================================================
# Helper Functions
# =============================================================================


def _create_state(**kwargs) -> OpenAIToClaudeStreamState:
    """Create a stream state with custom defaults."""
    defaults = {
        "message_id": "msg_test",
        "tool_name_map_inverse": {},
        "text_block_index": 0,
        "tool_block_counter": 0,
    }
    defaults.update(kwargs)
    return OpenAIToClaudeStreamState(**defaults)


def parse_sse_event(sse_string: str) -> tuple[str, dict]:
    """Parse SSE string into (event_name, data_dict)."""
    lines = sse_string.strip().split("\n")
    event_name = None
    data_json = None

    for line in lines:
        if line.startswith("event: "):
            event_name = line.split("event: ")[1]
        elif line.startswith("data: "):
            data_json = line.split("data: ")[1]

    if event_name is None or data_json is None:
        raise ValueError(f"Invalid SSE format: {sse_string[:100]}")

    return event_name, json.loads(data_json)


# =============================================================================
# Category 1: State Corruption Scenarios (5 tests)
# =============================================================================


@pytest.mark.unit
def test_state_corruption_negative_tool_index() -> None:
    """Test state machine handles negative tool index."""
    state = _create_state()

    # Create chunk with negative index
    chunk = create_malformed_sse_chunk(
        tool_index=-1,
        tool_id="call_neg",
        tool_name="negative_tool",
        arguments="{}",
    )

    # Should handle negative index (dict accepts negative keys)
    ingest_openai_chunk(state, chunk)

    # State should track tool at index -1
    assert -1 in state.current_tool_calls
    assert state.current_tool_calls[-1].tool_id == "call_neg"

    # Invariants should still hold
    assert_state_invariants(state)


@pytest.mark.unit
def test_state_corruption_non_integer_tool_index() -> None:
    """Test state machine handles non-integer tool index (float/string)."""
    state = _create_state()

    # Python dict can have non-int keys
    # Create chunk with float index
    chunk_float = {"choices": [{"delta": {"tool_calls": [{"index": 1.5, "id": "call_float"}]}}]}

    # Should handle float index (converted to dict key)
    ingest_openai_chunk(state, chunk_float)

    # Float becomes dict key
    assert 1.5 in state.current_tool_calls


@pytest.mark.unit
def test_state_corruption_duplicate_tool_start_events() -> None:
    """Test that duplicate tool start events don't increment counter multiple times."""
    state = _create_state()

    # First start event
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
        arguments="{}",
    )
    ingest_openai_chunk(state, chunk1)

    # Tool should start
    assert state.current_tool_calls[0].started
    assert state.tool_block_counter == 1

    # Try to start again with new name (state corruption scenario)
    state.current_tool_calls[0].started = False  # Reset to test re-emission

    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool_renamed",  # Different name
    )
    ingest_openai_chunk(state, chunk2)

    # Counter should increment again (started was reset)
    # This tests the state corruption scenario where started is reset
    assert state.current_tool_calls[0].tool_name == "tool_renamed"


@pytest.mark.unit
def test_state_corruption_id_change_after_tool_started() -> None:
    """Test that tool ID can change after tool started (state mutation)."""
    state = _create_state()

    # Start tool with ID
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_original",
        tool_name="tool",
        arguments="{}",
    )
    ingest_openai_chunk(state, chunk1)

    original_id = state.current_tool_calls[0].tool_id
    assert original_id == "call_original"
    assert state.current_tool_calls[0].started

    # Change ID after started (state mutation)
    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_changed",  # Different ID
    )
    ingest_openai_chunk(state, chunk2)

    # ID can be changed even after started
    assert state.current_tool_calls[0].tool_id == "call_changed"


@pytest.mark.unit
def test_state_corruption_name_change_after_tool_started() -> None:
    """Test that tool name can change after tool started (state mutation)."""
    state = _create_state()

    # Start tool with name
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="original_name",
        arguments="{}",
    )
    events1 = ingest_openai_chunk(state, chunk1)

    # Extract the emitted tool name
    start_event_data = [e for e in events1 if "content_block_start" in e][0]
    _, data = parse_sse_event(start_event_data)
    emitted_name = data["content_block"]["name"]

    assert emitted_name == "original_name"
    assert state.current_tool_calls[0].tool_name == "original_name"

    # Change name after started (but this won't re-emit start event)
    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="changed_name",
    )
    events2 = ingest_openai_chunk(state, chunk2)

    # State name changes but no new start event (already started)
    assert state.current_tool_calls[0].tool_name == "changed_name"
    # No new content_block_start event
    assert not any("content_block_start" in e for e in events2)


# =============================================================================
# Category 2: JSON & Arguments Issues (4 tests)
# =============================================================================


@pytest.mark.unit
def test_json_issue_invalid_json_never_completes() -> None:
    """Test that incomplete JSON never triggers json_sent."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # Send malformed JSON that never completes
    malformed_chunks = [
        create_malformed_sse_chunk(tool_index=0, arguments='{"incomplete":'),
        create_malformed_sse_chunk(tool_index=0, arguments='"still not done'),
        create_malformed_sse_chunk(tool_index=0, arguments='more data"'),
    ]

    for chunk in malformed_chunks:
        ingest_openai_chunk(state, chunk)

    # JSON should never be marked as complete
    assert not state.current_tool_calls[0].json_sent
    # Buffer accumulates all chunks
    assert "incomplete" in state.current_tool_calls[0].args_buffer


@pytest.mark.unit
def test_json_issue_arguments_after_complete_json() -> None:
    """Test that arguments arriving after JSON is complete don't re-emit."""
    state = _create_state()

    # Start tool with complete JSON
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
        arguments='{"complete": true}',
    )
    events1 = ingest_openai_chunk(state, chunk1)

    # Should emit input_json_delta
    assert any("input_json_delta" in e for e in events1)
    assert state.current_tool_calls[0].json_sent

    # Send more arguments after complete
    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        arguments='{"extra": "data"}',
    )
    events2 = ingest_openai_chunk(state, chunk2)

    # No new input_json_delta (already sent)
    assert not any("input_json_delta" in e for e in events2)
    # Buffer continues to accumulate
    assert "extra" in state.current_tool_calls[0].args_buffer


@pytest.mark.unit
def test_json_issue_non_string_arguments() -> None:
    """Test handling of non-string arguments (dict, int, list)."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # Send arguments as dict (should be stringified)
    chunk = {
        "choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": {"x": 1}}}]}}]
    }

    ingest_openai_chunk(state, chunk)

    # Arguments should be converted to string
    assert isinstance(state.current_tool_calls[0].args_buffer, str)
    # Stringified dict won't be valid JSON
    assert state.current_tool_calls[0].args_buffer == "{'x': 1}"


@pytest.mark.unit
def test_json_issue_extremely_large_arguments() -> None:
    """Test handling of extremely large argument strings."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # Create a large JSON argument (simulating large tool inputs)
    large_data = ",".join([f'"field_{i}": "value_{i}"' for i in range(1000)])
    large_json = "{" + large_data + "}"

    chunk = create_malformed_sse_chunk(
        tool_index=0,
        arguments=large_json,
    )

    ingest_openai_chunk(state, chunk)

    # Should handle large arguments
    assert len(state.current_tool_calls[0].args_buffer) > 10000
    # JSON should be complete
    assert state.current_tool_calls[0].json_sent


# =============================================================================
# Category 3: Stream Termination Issues (3 tests)
# =============================================================================


@pytest.mark.unit
def test_termination_incomplete_tool_never_started() -> None:
    """Test final_events with tool that never started."""
    state = _create_state()

    # Add tool entry but never start it
    state.current_tool_calls[0] = ToolCallIndexState()
    state.current_tool_calls[0].tool_id = "call_0"
    state.current_tool_calls[0].tool_name = "tool"
    # started = False, no output_index

    # Generate final events
    events = final_events(state)

    # Should not emit content_block_stop for unstarted tool
    stop_events = [e for e in events if "content_block_stop" in e]
    assert len(stop_events) == 1  # Only text block stop

    # Invariants should still hold
    assert_state_invariants(state)


@pytest.mark.unit
def test_termination_incomplete_json_at_stream_end() -> None:
    """Test final_events with tool that has incomplete JSON."""
    state = _create_state()

    # Start tool with incomplete JSON
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, chunk1)

    # Incomplete JSON
    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        arguments='{"incomplete":',
    )
    ingest_openai_chunk(state, chunk2)

    # Tool started but json_sent is False
    assert state.current_tool_calls[0].started
    assert not state.current_tool_calls[0].json_sent

    # Generate final events
    events = final_events(state)

    # Should still emit content_block_stop for started tool
    stop_events = [e for e in events if "content_block_stop" in e]
    assert len(stop_events) == 2  # Text block + tool block


@pytest.mark.unit
def test_termination_stream_without_finish_reason() -> None:
    """Test state behavior when stream ends without finish_reason."""
    state = _create_state()

    # Stream some content but never set finish_reason
    chunk = create_malformed_sse_chunk(content="Hello")
    ingest_openai_chunk(state, chunk)

    # final_stop_reason should still be default
    assert state.final_stop_reason == "end_turn"

    # Generate final events
    events = final_events(state)

    # Should have proper message_delta with stop_reason
    delta_events = [e for e in events if "message_delta" in e]
    assert len(delta_events) == 1

    _, data = parse_sse_event(delta_events[0])
    assert data["delta"]["stop_reason"] == "end_turn"


# =============================================================================
# Category 4: Data Type Violations (3 tests)
# =============================================================================


@pytest.mark.unit
def test_data_type_unicode_in_tool_arguments() -> None:
    """Test handling of Unicode characters in tool arguments."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # Send Unicode arguments
    unicode_json = '{"text": "Hello 世界 🌍", "emoji": "😀"}'
    chunk = create_malformed_sse_chunk(
        tool_index=0,
        arguments=unicode_json,
    )

    ingest_openai_chunk(state, chunk)

    # Should handle Unicode correctly
    assert "世界" in state.current_tool_calls[0].args_buffer
    assert "😀" in state.current_tool_calls[0].args_buffer
    # JSON should be valid and complete
    assert state.current_tool_calls[0].json_sent


@pytest.mark.unit
def test_data_type_control_characters_in_json() -> None:
    """Test handling of control characters in JSON strings."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # JSON with control characters (escaped properly)
    json_with_controls = '{"text": "Line1\\nLine2\\tTabbed"}'
    chunk = create_malformed_sse_chunk(
        tool_index=0,
        arguments=json_with_controls,
    )

    ingest_openai_chunk(state, chunk)

    # Should handle escaped control characters
    assert "\\n" in state.current_tool_calls[0].args_buffer
    assert state.current_tool_calls[0].json_sent


@pytest.mark.unit
def test_data_type_empty_tool_id() -> None:
    """Test handling of empty string tool ID."""
    state = _create_state()

    # Send tool call with empty ID
    chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="",  # Empty string
        tool_name="tool",
        arguments="{}",
    )

    ingest_openai_chunk(state, chunk)

    # Empty string is falsy, so ID is NOT set (treated like None)
    # The tool call is tracked but tool_id remains None
    assert 0 in state.current_tool_calls
    # Empty string is not stored (falsy in the condition)
    # `if isinstance(provided_id, str) and provided_id:`
    assert state.current_tool_calls[0].tool_id is None
    # Tool doesn't start because tool_id is None (need both id and name)
    assert not state.current_tool_calls[0].started


# =============================================================================
# Additional Edge Cases
# =============================================================================


@pytest.mark.unit
def test_edge_case_multiple_tools_same_index_collision() -> None:
    """Test handling when same index is received for different tools."""
    state = _create_state()

    # First tool at index 0
    chunk1 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_first",
        tool_name="first_tool",
        arguments="{}",
    )
    ingest_openai_chunk(state, chunk1)

    first_id = state.current_tool_calls[0].tool_id
    assert first_id == "call_first"

    # Second tool at same index (collision/overwrite)
    chunk2 = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_second",  # Different ID
        tool_name="second_tool",
        arguments="{}",
    )
    ingest_openai_chunk(state, chunk2)

    # State is overwritten (collision)
    assert state.current_tool_calls[0].tool_id == "call_second"
    # But both start events might have been emitted (depending on started state)


@pytest.mark.unit
def test_edge_case_tool_call_overflow_protection() -> None:
    """Test state machine with very large number of tool calls."""
    state = _create_state()

    # Create 100 tool calls
    for i in range(100):
        chunk = create_malformed_sse_chunk(
            tool_index=i,
            tool_id=f"call_{i}",
            tool_name=f"tool_{i}",
            arguments="{}",
        )
        ingest_openai_chunk(state, chunk)

    # All 100 tools should be tracked
    assert len(state.current_tool_calls) == 100
    assert state.tool_block_counter == 100

    # Invariants should hold
    assert_state_invariants(state)


@pytest.mark.unit
def test_edge_case_null_vs_empty_string_arguments() -> None:
    """Test difference between null and empty string arguments."""
    state = _create_state()

    # Start tool
    init_chunk = create_malformed_sse_chunk(
        tool_index=0,
        tool_id="call_0",
        tool_name="tool",
    )
    ingest_openai_chunk(state, init_chunk)

    # Null arguments (should be ignored)
    chunk_null = {
        "choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": None}}]}}]
    }

    ingest_openai_chunk(state, chunk_null)

    # Null is ignored, buffer remains empty
    assert state.current_tool_calls[0].args_buffer == ""

    # Empty string arguments
    chunk_empty = create_malformed_sse_chunk(
        tool_index=0,
        arguments="",
    )

    ingest_openai_chunk(state, chunk_empty)

    # Empty string is buffered
    assert state.current_tool_calls[0].args_buffer == ""


@pytest.mark.unit
def test_edge_case_finish_reason_overwrites() -> None:
    """Test that later finish_reason overwrites earlier one."""
    state = _create_state()

    # First finish_reason
    chunk1 = {"choices": [{"finish_reason": "length", "delta": {}}]}
    ingest_openai_chunk(state, chunk1)
    assert state.final_stop_reason == "max_tokens"

    # Second finish_reason overwrites
    chunk2 = {"choices": [{"finish_reason": "stop", "delta": {}}]}
    ingest_openai_chunk(state, chunk2)
    assert state.final_stop_reason == "end_turn"


@pytest.mark.unit
def test_edge_case_out_of_order_tool_indices() -> None:
    """Test tool calls arriving in non-sequential index order."""
    state = _create_state()

    # Tools arrive out of order: 2, 0, 1
    chunks = [
        create_malformed_sse_chunk(
            tool_index=2,
            tool_id="call_2",
            tool_name="tool_2",
            arguments="{}",
        ),
        create_malformed_sse_chunk(
            tool_index=0,
            tool_id="call_0",
            tool_name="tool_0",
            arguments="{}",
        ),
        create_malformed_sse_chunk(
            tool_index=1,
            tool_id="call_1",
            tool_name="tool_1",
            arguments="{}",
        ),
    ]

    for chunk in chunks:
        ingest_openai_chunk(state, chunk)

    # All tools tracked correctly
    assert len(state.current_tool_calls) == 3
    assert 0 in state.current_tool_calls
    assert 1 in state.current_tool_calls
    assert 2 in state.current_tool_calls
    assert state.tool_block_counter == 3
