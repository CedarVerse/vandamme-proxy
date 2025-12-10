"""
Middleware System for Vandamme Proxy

Provides an elegant middleware chain for processing requests and responses,
enabling provider-specific enhancements without intruding into core logic.

Architecture:
    - MiddlewareChain: Orchestrates execution of registered middlewares
    - Middleware: Abstract base for all middleware implementations
    - RequestContext/ResponseContext: Immutable data containers

Design Principles:
    - Clean separation of concerns
    - Minimal intrusion into existing code
    - Extensible for future provider needs
    - Type-safe and async-first
"""

from .base import Middleware, MiddlewareChain, RequestContext, ResponseContext
from .thought_signature import ThoughtSignatureMiddleware

__all__ = [
    "Middleware",
    "MiddlewareChain",
    "RequestContext",
    "ResponseContext",
    "ThoughtSignatureMiddleware",
]
