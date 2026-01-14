"""Runtime ModelManager accessor (following get_config pattern).

This module provides wiring helpers for accessing ModelManager from app.state
without relying on a global singleton.

This module intentionally contains *only* wiring helpers (no import-time side
effects). It exists so API layers can retrieve the ModelManager instance owned
by the FastAPI app without relying on a module-level singleton.

Invariants:
- The ModelManager is created once at app startup and stored on `app.state`.
- Endpoints access it via `request.app.state.model_manager`.
"""

from __future__ import annotations

from fastapi import Request

from src.core.model_manager import ModelManager


def get_model_manager(request: Request) -> ModelManager:
    """Return the ModelManager instance owned by the FastAPI app.

    This is the preferred way to access ModelManager in API endpoints.

    Usage:
        from src.core.model_manager_runtime import get_model_manager
        from fastapi import Depends

        def my_endpoint(mm: ModelManager = Depends(get_model_manager)):
            provider, model = mm.resolve_model("haiku")

    Args:
        request: The FastAPI Request object.

    Returns:
        The ModelManager instance from app.state.

    Raises:
        RuntimeError: If ModelManager is not configured on app.state.
        TypeError: If app.state.model_manager is not a ModelManager instance.
    """
    mm = getattr(request.app.state, "model_manager", None)
    if mm is None:
        raise RuntimeError("ModelManager is not configured on app.state")
    if not isinstance(mm, ModelManager):
        raise TypeError("app.state.model_manager is not a ModelManager instance")
    return mm
