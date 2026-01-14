"""Runtime MiddlewareProcessor accessor (following get_config pattern).

This module provides wiring helpers for accessing MiddlewareProcessor from app.state
without relying on a global singleton.

This module intentionally contains *only* wiring helpers (no import-time side
effects). It exists so API layers can retrieve the MiddlewareProcessor instance
owned by the FastAPI app without relying on a module-level singleton.

Invariants:
- The MiddlewareProcessor is created once at app startup and stored on `app.state`.
- Endpoints access it via `request.app.state.middleware_processor`.
"""

from __future__ import annotations

from fastapi import Request

from src.api.middleware_integration import MiddlewareAwareRequestProcessor


def get_middleware_processor(request: Request) -> MiddlewareAwareRequestProcessor:
    """Return the MiddlewareProcessor instance owned by the FastAPI app.

    This is the preferred way to access MiddlewareProcessor in API endpoints.

    Usage:
        from src.api.middleware_runtime import get_middleware_processor
        from fastapi import Depends

        def my_endpoint(proc: MiddlewareAwareRequestProcessor = Depends(get_middleware_processor)):
            await proc.process_request(request_context)

    Args:
        request: The FastAPI Request object.

    Returns:
        The MiddlewareProcessor instance from app.state.

    Raises:
        RuntimeError: If MiddlewareProcessor is not configured on app.state.
        TypeError: If app.state.middleware_processor is not a
            MiddlewareAwareRequestProcessor instance.
    """
    proc = getattr(request.app.state, "middleware_processor", None)
    if proc is None:
        raise RuntimeError("MiddlewareProcessor is not configured on app.state")
    if not isinstance(proc, MiddlewareAwareRequestProcessor):
        raise TypeError(
            "app.state.middleware_processor is not a MiddlewareAwareRequestProcessor instance"
        )
    return proc
