"""Utility functions for message validation and inspection.

This module provides predicate functions that encapsulate complex validation
logic for Claude messages, improving readability and testability.

The extracted predicates reduce deep nesting in request_converter.py by
providing self-documenting boolean checks.
"""

from src.core.constants import Constants
from src.models.claude import ClaudeMessage


def is_tool_result_message(msg: ClaudeMessage) -> bool:
    """Check if a message contains tool result content blocks.

    A tool result message is a user message containing one or more
    CONTENT_TOOL_RESULT blocks, which contain the results of tool
    executions that should be paired with preceding tool_use blocks.

    Args:
        msg: The Claude message to check.

    Returns:
        True if the message is a user message containing tool results,
        False otherwise.
    """
    if msg.role != Constants.ROLE_USER:
        return False
    if not isinstance(msg.content, list):
        return False
    return any(
        hasattr(block, "type") and block.type == Constants.CONTENT_TOOL_RESULT
        for block in msg.content
    )


def should_consume_tool_results(messages: list[ClaudeMessage], index: int) -> bool:
    """Check if we should consume tool results following an assistant message.

    In Claude's API, tool results are sent as a separate user message that
    immediately follows an assistant message containing tool_use blocks.
    This function checks if the next message is such a tool result message.

    Args:
        messages: The list of Claude messages.
        index: The current index in the message list (typically an assistant
            message position).

    Returns:
        True if the next message exists and contains tool results that
        should be consumed, False otherwise.
    """
    if index + 1 >= len(messages):
        return False
    return is_tool_result_message(messages[index + 1])
