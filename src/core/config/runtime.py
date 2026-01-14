"""Runtime config accessor (following RequestTracker pattern).

This module intentionally contains *only* wiring helpers (no import-time side
effects). It exists so API layers can retrieve the Config instance owned by
the FastAPI app without relying on a global singleton.

Invariants:
- The config is created once at app startup and stored on `app.state`.
- Endpoints access it via `request.app.state.config`.
"""

from __future__ import annotations

from fastapi import Request

from .config import Config


def get_config(request: Request) -> Config:
    """Return the Config instance owned by the FastAPI app.

    This is the preferred way to access config in API endpoints.
    Usage:
        def my_endpoint(request: Request, cfg: Config = Depends(get_config)):
            host = cfg.host
    """
    cfg = getattr(request.app.state, "config", None)
    if cfg is None:
        raise RuntimeError("Config is not configured on app.state")
    if not isinstance(cfg, Config):
        raise TypeError("app.state.config is not a Config instance")
    return cfg
