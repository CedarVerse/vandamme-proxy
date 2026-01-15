"""Decorators for safe operations with automatic error handling."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger(__name__)


def log_and_return_default(
    *,
    default: R,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    context: str = "",
    log_level: int = logging.WARNING,
    include_traceback: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that logs exceptions and returns a default value.

    Use this for operations where failure is non-critical and a fallback
    value is available.

    Args:
        default: Value to return on exception
        exceptions: Exception types to catch (be specific!)
        context: Description for log messages
        log_level: Logging level for exceptions
        include_traceback: Whether to log full traceback

    Example:
        @log_and_return_default(
            default={},
            exceptions=(OSError, json.JSONDecodeError),
            context="Config file loading",
            log_level=logging.WARNING
        )
        def load_config_file(path: str) -> dict:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                msg = f"{context or func.__name__}: {type(e).__name__}: {e}"
                logger.log(log_level, msg, exc_info=include_traceback)
                return default

        return wrapper

    return decorator


def log_and_reraise(
    *,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    context: str = "",
    log_level: int = logging.ERROR,
    reraise_type: type[Exception] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that logs exceptions and re-raises them (optionally wrapped).

    Use this when you want visibility into exceptions before they propagate.

    Example:
        @log_and_reraise(
            exceptions=(httpx.TimeoutError, httpx.NetworkError),
            context="Upstream request",
            log_level=logging.WARNING
        )
        async def fetch_upstream():
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]
            except exceptions as e:
                msg = f"{context or func.__name__}: {type(e).__name__}: {e}"
                logger.log(log_level, msg, exc_info=True)
                if reraise_type:
                    raise reraise_type(msg) from e
                raise

        return async_wrapper  # type: ignore[return-value]

    return decorator
