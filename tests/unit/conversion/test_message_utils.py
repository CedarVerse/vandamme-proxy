"""Tests for message utility functions.

These tests verify the behavior of the predicate functions that
validate and inspect Claude messages.
"""

import pytest

from src.conversion.request_converter import (
    _is_tool_result_message,
    _should_consume_tool_results,
)
from src.core.constants import Constants
from src.models.claude import (
    ClaudeContentBlockText,
    ClaudeContentBlockToolResult,
    ClaudeContentBlockToolUse,
    ClaudeMessage,
)


@pytest.mark.unit
class TestIsToolResultMessage:
    """Tests for _is_tool_result_message predicate."""

    def test_returns_false_for_assistant_message(self):
        """Assistant messages are not tool result messages."""
        msg = ClaudeMessage(role=Constants.ROLE_ASSISTANT, content="Hello")
        assert _is_tool_result_message(msg) is False

    def test_returns_false_for_user_message_with_string_content(self):
        """User messages with string content are not tool result messages."""
        msg = ClaudeMessage(role=Constants.ROLE_USER, content="Hello")
        assert _is_tool_result_message(msg) is False

    def test_returns_false_for_user_message_with_text_blocks(self):
        """User messages with text blocks are not tool result messages."""
        msg = ClaudeMessage(
            role=Constants.ROLE_USER,
            content=[
                ClaudeContentBlockText(type="text", text="Hello"),
            ],
        )
        assert _is_tool_result_message(msg) is False

    def test_returns_true_for_user_message_with_tool_result_blocks(self):
        """User messages with tool result blocks should return True."""
        msg = ClaudeMessage(
            role=Constants.ROLE_USER,
            content=[
                ClaudeContentBlockToolResult(
                    type="tool_result",
                    tool_use_id="tool_123",
                    content="Result",
                ),
            ],
        )
        assert _is_tool_result_message(msg) is True

    def test_returns_true_for_mixed_content_including_tool_results(self):
        """User messages with mixed content including tool results should return True."""
        msg = ClaudeMessage(
            role=Constants.ROLE_USER,
            content=[
                ClaudeContentBlockText(type="text", text="Here are the results:"),
                ClaudeContentBlockToolResult(
                    type="tool_result",
                    tool_use_id="tool_123",
                    content="Result",
                ),
            ],
        )
        assert _is_tool_result_message(msg) is True


@pytest.mark.unit
class TestShouldConsumeToolResults:
    """Tests for _should_consume_tool_results predicate."""

    def test_returns_false_when_at_last_message(self):
        """When at the last message, there's no next message to consume."""
        messages = [
            ClaudeMessage(role=Constants.ROLE_USER, content="First"),
        ]
        assert _should_consume_tool_results(messages, 0) is False

    def test_returns_false_when_next_message_is_not_tool_result(self):
        """When next message is not a tool result message, should not consume."""
        messages = [
            ClaudeMessage(role=Constants.ROLE_ASSISTANT, content="Response"),
            ClaudeMessage(role=Constants.ROLE_USER, content="Follow-up"),
        ]
        assert _should_consume_tool_results(messages, 0) is False

    def test_returns_true_when_next_message_is_tool_result(self):
        """When next message is a tool result message, should consume."""
        messages = [
            ClaudeMessage(
                role=Constants.ROLE_ASSISTANT,
                content=[
                    ClaudeContentBlockToolUse(
                        type="tool_use",
                        id="tool_123",
                        name="search",
                        input={"query": "test"},
                    )
                ],
            ),
            ClaudeMessage(
                role=Constants.ROLE_USER,
                content=[
                    ClaudeContentBlockToolResult(
                        type="tool_result",
                        tool_use_id="tool_123",
                        content="Search results",
                    )
                ],
            ),
        ]
        assert _should_consume_tool_results(messages, 0) is True

    def test_returns_false_at_second_to_last_message_without_tool_results(self):
        """Even at second-to-last, should return False if next message is not tool result."""
        messages = [
            ClaudeMessage(role=Constants.ROLE_USER, content="First"),
            ClaudeMessage(role=Constants.ROLE_USER, content="Second"),
            ClaudeMessage(role=Constants.ROLE_ASSISTANT, content="Response"),
        ]
        assert _should_consume_tool_results(messages, 1) is False
