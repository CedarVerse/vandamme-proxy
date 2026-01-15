"""Safe parsing operations with proper exception handling and logging.

These functions replace bare except clauses with specific exception handling
while maintaining existing fallback behavior.
"""

from __future__ import annotations

import json
import logging
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Specific exceptions that are actually expected and recoverable during JSON parsing
JSON_PARSE_EXCEPTIONS = (json.JSONDecodeError, TypeError, ValueError, OverflowError)


def safe_json_loads(
    value: str | None,
    *,
    default: T,
    context: str = "",
    log_level: int = logging.DEBUG,
) -> T:
    """Parse JSON with specific exception handling and optional logging.

    Replaces bare `except Exception:` with specific JSON parse exceptions.

    Args:
        value: JSON string to parse
        default: Fallback value on parse failure
        context: Description for logging (e.g., "SSE event parsing")
        log_level: Logging level (DEBUG for expected failures, WARNING for unexpected)

    Returns:
        Parsed value or default

    Examples:
        >>> # Before (bare except)
        >>> try:
        >>>     return json.loads(value)
        >>> except Exception:
        >>>     return default

        >>> # After (specific)
        >>> from src.core.safe_ops import safe_json_loads
        >>> data = safe_json_loads(raw, default={}, context="tool arguments")
    """
    if not value:
        return default

    try:
        return json.loads(value)  # type: ignore[no-any-return]
    except JSON_PARSE_EXCEPTIONS as e:
        # These are expected parse errors - log at specified level
        if context:
            logger.log(log_level, f"{context}: JSON parse error: {e}")
        return default
