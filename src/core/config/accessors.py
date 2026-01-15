"""Runtime config value accessors.

These functions provide config values at runtime without requiring
direct config imports. They're used to replace module-level constants
that would otherwise create import-time coupling.

Usage:
    # Instead of:
    LOG_REQUEST_METRICS = config.log_request_metrics

    # Use:
    from src.core.config.accessors import log_request_metrics
    if log_request_metrics():
        ...
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


def _get_config_from_context() -> Config | None:
    """Get config from FastAPI request context if available.

    Returns None if not in a request context (e.g., CLI, tests).
    This allows the same functions to work in multiple contexts.

    In tests, config is provided via dependency injection fixtures.
    In CLI, config is created explicitly per command.

    Stack inspection is expensive and fragile, so we use specific exceptions
    and log failures to aid debugging. This function is called frequently
    during request processing, so failures are logged at DEBUG level.
    """
    try:
        # Try to get from FastAPI request context by inspecting the call stack
        import inspect

        for frame_info in inspect.stack():
            try:
                frame_locals = frame_info.frame.f_locals
            except (AttributeError, ValueError, RuntimeError):
                # Frame unavailable or corrupted - stop iterating
                break

            if "request" in frame_locals:
                from fastapi import Request

                request = frame_locals["request"]
                if isinstance(request, Request):
                    return getattr(request.app.state, "config", None)
    except (AttributeError, ValueError, RuntimeError, ImportError) as e:
        # Stack inspection failed - expected in non-request contexts
        # Log at DEBUG to avoid noise while still providing visibility
        logger.debug(f"Stack inspection for config context failed: {type(e).__name__}: {e}")
    return None


def _get_global_fallback() -> Config:
    """Fallback to module-level config for non-request contexts.

    This is used for CLI commands and test scenarios where there's
    no FastAPI request context. It creates a singleton only when needed.

    TODO: Eventually remove this after CLI migration is complete.
    """
    # Lazy import to avoid circular dependency
    from .config import Config

    return Config()


# Runtime accessor functions
# These can be used anywhere without creating import-time coupling


def log_request_metrics() -> bool:
    """Get the log_request_metrics config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.log_request_metrics


def max_tokens_limit() -> int:
    """Get the max_tokens_limit config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.max_tokens_limit


def min_tokens_limit() -> int:
    """Get the min_tokens_limit config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.min_tokens_limit


def request_timeout() -> int:
    """Get the request_timeout config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.request_timeout


def streaming_read_timeout() -> float | None:
    """Get the streaming_read_timeout config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.streaming_read_timeout


def streaming_connect_timeout() -> float:
    """Get the streaming_connect_timeout config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.streaming_connect_timeout


def models_cache_enabled() -> bool:
    """Get the models_cache_enabled config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.models_cache_enabled


def cache_dir() -> str:
    """Get the cache_dir config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.cache_dir


def models_cache_ttl_hours() -> int:
    """Get the models_cache_ttl_hours config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.models_cache_ttl_hours


def active_requests_sse_enabled() -> bool:
    """Get the active_requests_sse_enabled config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.active_requests_sse_enabled


def active_requests_sse_interval() -> float:
    """Get the active_requests_sse_interval config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.active_requests_sse_interval


def active_requests_sse_heartbeat() -> float:
    """Get the active_requests_sse_heartbeat config value."""
    cfg = _get_config_from_context()
    if cfg is None:
        cfg = _get_global_fallback()
    return cfg.active_requests_sse_heartbeat
