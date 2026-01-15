"""Context managers for scoped error handling."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Generator
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextlib.contextmanager
def suppress_and_log(
    *exceptions: type[Exception],
    context: str = "",
    log_level: int = logging.WARNING,
    log_result: bool = False,
) -> Generator[None, None, None]:
    """Context manager that suppresses exceptions after logging them.

    Use this to replace bare `except: pass` blocks.

    Args:
        *exceptions: Specific exception types to suppress
        context: Description for log messages
        log_level: Logging level
        log_result: If True, logs "success" message on no exception

    Example:
        >>> # Before
        >>> try:
        >>>     cleanup_task()
        >>> except Exception:
        >>>     pass

        >>> # After
        >>> with suppress_and_log(
        >>>     asyncio.CancelledError, Exception,
        >>>     context="Background cleanup"
        >>> ):
        >>>     cleanup_task()
    """
    try:
        yield
        if log_result:
            logger.debug(f"{context}: completed successfully")
    except exceptions as e:
        msg = f"{context}: {type(e).__name__}: {e}"
        logger.log(log_level, msg, exc_info=False)


@contextlib.contextmanager
def soft_fail(
    *,
    fallback_value: T,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    context: str = "",
    log_level: int = logging.WARNING,
) -> Generator[list[T], None, None]:
    """Context manager for operations that should soft-fail with a fallback.

    Returns a mutable list where the first element is either the result
    or the fallback value.

    Example:
        >>> with soft_fail(fallback_value={}, context="Cache load") as result:
        >>>     result[0] = load_from_cache()
        >>> data = result[0]
    """
    result: list[T] = [fallback_value]
    try:
        yield result
    except exceptions as e:
        msg = f"{context or 'operation'}: {type(e).__name__}: {e}"
        logger.log(log_level, msg, exc_info=False)
        result[0] = fallback_value
