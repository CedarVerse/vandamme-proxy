"""Metrics helper functions for request tracking.

This module provides utility functions for populating request metrics,
reducing code duplication and improving maintainability.
"""

import json
from typing import Any

from src.core.constants import Constants
from src.models.claude import ClaudeMessagesRequest


def count_tool_calls(request: ClaudeMessagesRequest) -> tuple[int, int]:
    """Count tool_use and tool_result blocks in a Claude request.

    Args:
        request: The Claude request to count tool calls from.

    Returns:
        A tuple of (tool_use_count, tool_result_count).
    """
    tool_use_count = 0
    tool_result_count = 0

    for message in request.messages:
        if isinstance(message.content, list):
            for block in message.content:
                if hasattr(block, "type"):
                    if block.type == Constants.CONTENT_TOOL_USE:
                        tool_use_count += 1
                    elif block.type == Constants.CONTENT_TOOL_RESULT:
                        tool_result_count += 1

    return tool_use_count, tool_result_count


def populate_request_metrics(
    *,
    metrics: Any | None,
    request: ClaudeMessagesRequest,
) -> tuple[int, int, int]:
    """Populate request metrics with message count, request size, and tool counts.

    This function handles both enabled and disabled metrics scenarios,
    avoiding dual-path duplication in endpoint code.

    Args:
        metrics: The RequestMetrics object to populate, or None if metrics disabled.
        request: The Claude request to extract metrics from.

    Returns:
        A tuple of (message_count, request_size, tool_use_count) for logging purposes.
        When metrics is disabled, returns simplified counts.
    """
    # Calculate request size
    request_size = len(json.dumps(request.model_dump(exclude_none=True)))

    # Count tool uses and tool results
    tool_use_count, tool_result_count = count_tool_calls(request)

    # Count messages including system message
    message_count = len(request.messages)
    if request.system:
        if isinstance(request.system, str):
            message_count += 1
        elif isinstance(request.system, list):
            message_count += len(request.system)

    # Populate metrics if enabled
    if metrics is not None:
        metrics.request_size = request_size
        metrics.message_count = message_count
        metrics.tool_use_count = tool_use_count
        metrics.tool_result_count = tool_result_count

    return message_count, request_size, tool_use_count
