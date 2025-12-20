from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.top_models.types import TopModel, TopModelsSourceName


class TopModelsSourceError(RuntimeError):
    pass


class TopModelsSource(Protocol):
    name: TopModelsSourceName

    async def fetch_models(self) -> tuple[TopModel, ...]:
        """Fetch and normalize a list of models from the upstream source."""


@dataclass(frozen=True, slots=True)
class TopModelsSourceConfig:
    timeout_seconds: float
