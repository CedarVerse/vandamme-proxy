"""Structured error types for dashboard operations."""

from dataclasses import dataclass
from enum import Enum


class ModelsFetchErrorType(Enum):
    """Classification of models fetch failures."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTH = "auth"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelsFetchError:
    """Structured error with context for elegant display."""

    type: ModelsFetchErrorType
    provider: str | None
    message: str
    suggestion: str | None = None
