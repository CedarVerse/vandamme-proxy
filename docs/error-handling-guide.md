# Error Handling Guide

## Principles

1. **Be Specific**: Catch only exceptions you can handle
2. **Always Log**: Log before falling back
3. **Use Safe Ops**: Import from `src.core.safe_ops`
4. **Context Matters**: Different contexts need different handling

## Common Patterns

### JSON Parsing

Use the `safe_json_loads` function for safe JSON parsing with specific exception handling:

```python
from src.core.safe_ops import safe_json_loads

# Instead of:
# try:
#     data = json.loads(raw_json)
# except Exception:
#     data = {}

# Use:
data = safe_json_loads(raw_json, default={}, context="Feature X")
```

**Why**: Catches only `JSON_PARSE_EXCEPTIONS` (json.JSONDecodeError, TypeError, ValueError, OverflowError) and logs failures at DEBUG level.

### SSE Event Parsing

For Server-Sent Events (SSE) parsing, use specific JSON exceptions:

```python
from src.core.safe_ops import JSON_PARSE_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)

try:
    payload = json.loads(ev.data)
except JSON_PARSE_EXCEPTIONS as e:
    # Expected during malformed SSE events
    logger.debug(f"SSE event parse error: {type(e).__name__}: {e}")
    continue
```

**Why**: SSE events can be malformed during streaming. Logging at DEBUG avoids noise while providing visibility.

### Optional Operations

Use the `suppress_and_log` context manager for operations that should soft-fail:

```python
from src.core.safe_ops import suppress_and_log

with suppress_and_log(
    (OSError, IOError),
    context="Cache cleanup"
):
    cleanup_cache_files()
```

**Why**: Provides clean syntax with automatic logging before suppression.

### Error Response Parsing

For HTTP error response parsing with fallbacks:

```python
import json
import logging

logger = logging.getLogger(__name__)

try:
    error_detail = e.response.json()
except (json.JSONDecodeError, ValueError, TypeError) as parse_err:
    # Failed to parse error response as JSON
    logger.debug(f"Failed to parse error response: {parse_err}")
    try:
        error_detail = e.response.text
    except (AttributeError, OSError) as text_err:
        # Final fallback: string representation
        logger.warning(f"Failed to extract error response text: {text_err}")
        error_detail = str(e)
```

**Why**: Graceful degradation through multiple fallback strategies with logging at each step.

### Cache Deserialization

For cache operations, specific deserialization exceptions:

```python
try:
    return self._deserialize(cache_data)
except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
    # Specific exceptions that occur during JSON deserialization
    logger.debug(f"Cache deserialization failed: {type(e).__name__}: {e}")
    return None
except Exception as unexpected:
    # Truly unexpected errors - log at WARNING for visibility
    logger.warning(f"Unexpected cache deserialization error: {type(unexpected).__name__}: {unexpected}")
    return None
```

**Why**: Separates expected parse failures from unexpected errors with different log levels.

### Streaming Error Propagation

For streaming contexts where errors should propagate:

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

except (asyncio.TimeoutError, asyncio.CancelledError):
    # Let timeout and cancellation errors propagate for SSE wrapper handling
    logger.debug("Timeout/cancellation in streaming, propagating to SSE wrapper")
    raise
except Exception as unexpected:
    # Any other exception is truly unexpected and should be logged
    logger.error(f"Unexpected error in streaming: {type(unexpected).__name__}: {unexpected}")
    raise
```

**Why**: Preserves original exception types for upstream handlers while logging for visibility.

## Exception Categories

### Expected and Recoverable
These should be caught and handled gracefully:
- `json.JSONDecodeError` - Malformed JSON during streaming
- `ValueError` - Invalid values
- `TypeError` - Type mismatches
- `KeyError` - Missing dictionary keys
- `AttributeError` - Missing attributes (when checking optional features)
- `OSError`, `IOError` - File system errors
- `httpx.HTTPError` - Network/HTTP errors
- `asyncio.TimeoutError`, `asyncio.CancelledError` - Async operation control

### Unexpected and Should Log
These should be caught for logging but indicate real issues:
- Most other `Exception` types that aren't specifically handled
- Use `logger.error()` or `logger.warning()` for visibility

### Should Always Propagate
These should typically NOT be caught:
- `SystemExit`, `KeyboardInterrupt` - Process control
- `MemoryError` - Critical system state
- `BaseException` - Root of all exceptions

## Log Levels

- **DEBUG**: Expected failures during normal operation (malformed SSE events, incomplete JSON during streaming)
- **WARNING**: Unexpected but recoverable errors (cache deserialization failures, missing optional features)
- **ERROR**: Truly unexpected errors that may indicate bugs (unexpected exceptions in core logic)

## Testing Error Handling

When testing error handling code:

```python
import pytest
from src.core.safe_ops import JSON_PARSE_EXCEPTIONS

def test_malformed_json_handling():
    """Test that malformed JSON is handled gracefully."""
    result = safe_json_loads("invalid json", default={}, context="test")
    assert result == {}

def test_exception_logging(caplog):
    """Test that exceptions are logged at appropriate levels."""
    with caplog.at_level(logging.DEBUG):
        result = safe_json_loads("{bad}", default={})
        assert "JSON parse error" in caplog.text
```

## Migration Guide

When migrating existing code from bare `except Exception`:

1. Identify what exceptions can actually occur in the try block
2. Group them by "expected/recoverable" vs "unexpected"
3. Add appropriate logging
4. Use specific exception tuples
5. Preserve existing fallback behavior

**Before:**
```python
try:
    data = json.loads(value)
except Exception:
    data = None
```

**After:**
```python
from src.core.safe_ops import JSON_PARSE_EXCEPTIONS

try:
    data = json.loads(value)
except JSON_PARSE_EXCEPTIONS as e:
    logger.debug(f"JSON parse failed: {e}")
    data = None
```

## Further Reading

- `src/core/safe_ops/` - Reusable error handling utilities
- Python Exception Hierarchy: https://docs.python.org/3/library/exceptions.html
- Logging Best Practices: https://docs.python.org/3/howto/logging.html
