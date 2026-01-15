from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from src.core.safe_ops import JSON_PARSE_EXCEPTIONS

logger = logging.getLogger(__name__)


@dataclass
class ToolCallIndexState:
    """Shared per-index tool-call state used across streaming translators."""

    tool_id: str | None = None
    tool_name: str | None = None
    args_buffer: str = ""
    started: bool = False
    json_sent: bool = False

    # Some translations need to remember an output-specific index for emitting deltas.
    output_index: str | None = None


class ToolCallIdAllocator:
    """Provides stable tool call ids per tool index."""

    def __init__(self, *, id_prefix: str) -> None:
        self._id_prefix = id_prefix
        self._ids: dict[int, str] = {}

    def get(self, index: int, *, provided_id: str | None = None) -> str:
        if provided_id:
            self._ids[index] = provided_id
            return provided_id
        if index not in self._ids:
            self._ids[index] = f"{self._id_prefix}-{index}"
        return self._ids[index]


class ToolCallArgsAssembler:
    """Accumulates argument deltas and detects JSON completeness."""

    def __init__(self) -> None:
        self._buffers: dict[int, str] = {}

    def append(self, index: int, delta: str) -> str:
        buf = self._buffers.get(index, "") + delta
        self._buffers[index] = buf
        return buf

    @staticmethod
    def is_complete_json(s: str) -> bool:
        """Check if string is complete JSON.

        Logs incomplete JSON at DEBUG level to aid debugging without
        creating noise during normal streaming operations.
        """
        try:
            json.loads(s)
            return True
        except JSON_PARSE_EXCEPTIONS:
            # Expected during streaming - log at DEBUG
            logger.debug(f"Incomplete JSON detected: {s[:50]}...")
            return False


def coerce_tool_name(name: Any) -> str | None:
    return name if isinstance(name, str) and name else None


def coerce_tool_id(tool_id: Any) -> str | None:
    return tool_id if isinstance(tool_id, str) and tool_id else None
