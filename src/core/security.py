"""src.core.security

Security utilities used across the proxy.

Design goals:
- **Stateless**: importing this module must never mutate global state.
- **Composable**: functions are usable from logging formatters, API code, and tests.
- **Safe-by-default**: helpers aim to prevent accidental credential leakage in logs.

This module intentionally contains *only* pure helpers. It does not define logging
handlers, formatters, or any initialization logic.
"""

from __future__ import annotations

import hashlib
import logging
import re

logger = logging.getLogger(__name__)


def get_api_key_hash(api_key: str) -> str:
    """Return an 8-char stable hash for an API key.

    Why:
        We want a value that is:
        - safe to log (non-reversible)
        - stable across runs (to correlate incidents)
        - short enough for human scanning

    Notes:
        The input is expected to be the *raw* key value.

    Args:
        api_key: Raw API key string.

    Returns:
        "REDACTED" for empty/sentinel values, otherwise the first 8 chars of
        the SHA-256 hash.
    """

    if not api_key or api_key == "REDACTED":
        return "REDACTED"
    # nosemgrep: py.weak-sensitive-data-hashing
    # SHA-256 first-8-char is appropriate for logging correlation IDs:
    # - Non-reversible: cannot recover original API key
    # - Stable: same key produces same hash across runs
    # - Purpose: debugging/incident correlation, not cryptography
    return hashlib.sha256(api_key.encode()).hexdigest()[:8]


def hash_api_keys_in_message(message: str) -> str:
    """Replace likely API keys in a message with stable short hashes.

    Why:
        We log upstream requests/responses and headers for debugging.
        These logs must not leak sensitive tokens.

    What this function does:
        - detects common API key patterns and replaces the secret with a hash
        - preserves enough structure (e.g., "Bearer <hash>") to be useful

    The patterns here are intentionally conservative and aim to avoid false
    positives while catching typical key formats.

    Args:
        message: Arbitrary log message.

    Returns:
        The message with secrets replaced.
    """

    if not message:
        return message

    # Pattern for API keys in various formats.
    # Matches: sk-xxx, Bearer xxx, x-api-key: xxx, "api_key": "xxx"
    from collections.abc import Callable
    from re import Match

    substitutions: list[tuple[str, Callable[[Match[str]], str]]] = [
        (r"(sk-[a-zA-Z0-9]{20,})", lambda m: f"sk-{get_api_key_hash(m.group(1)[3:])}"),
        (
            r"(Bearer\s+[a-zA-Z0-9\-_\.]{20,})",
            lambda m: f"Bearer {get_api_key_hash(m.group(0)[7:])}",
        ),
        (
            r"(x-api-key:\s*[a-zA-Z0-9\-_\.]{20,})",
            lambda m: f"x-api-key: {get_api_key_hash(m.group(0)[11:])}",
        ),
        (
            r"(\"api_key\":\s*\"[a-zA-Z0-9\-_\.]{20,}\")",
            lambda m: f'"api_key": "{get_api_key_hash(m.group(0)[13:-1])}"',
        ),
    ]

    redacted = message
    for pattern, replacement in substitutions:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)

    return redacted


def safe_exception_message(
    exception: Exception,
    include_debug: bool = False,
) -> str:
    """Return a safe error message from an exception for API responses.

    This function prevents stack trace exposure in client-facing error messages
    while preserving full details in server logs when debug mode is enabled.

    Args:
        exception: The exception to format.
        include_debug: If True, include exception type and message.
                      If False, return a generic message without internal details.

    Returns:
        A safe error message. Stack traces are NEVER included in API responses.
        They go to server logs only via logger.debug(exc_info=True).

    Examples:
        >>> safe_exception_message(ValueError("invalid input"), include_debug=False)
        'An error occurred while processing your request'

        >>> safe_exception_message(ValueError("invalid input"), include_debug=True)
        'ValueError: invalid input'
    """
    if include_debug:
        # Debug mode: include exception type and message (but never stack trace)
        return f"{type(exception).__name__}: {str(exception)}"
    else:
        # Production mode: generic message without internal details
        return "An error occurred while processing your request"
