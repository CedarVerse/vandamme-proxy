from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

TopModelsSourceName = Literal["openrouter"]


@dataclass(frozen=True, slots=True)
class TopModelPricing:
    input_per_million: float | None = None
    output_per_million: float | None = None

    @property
    def average_per_million(self) -> float | None:
        if self.input_per_million is None or self.output_per_million is None:
            return None
        return (self.input_per_million + self.output_per_million) / 2.0


@dataclass(frozen=True, slots=True)
class TopModel:
    id: str
    name: str | None
    provider: str
    sub_provider: str | None
    context_window: int | None
    capabilities: tuple[str, ...]
    pricing: TopModelPricing


@dataclass(frozen=True, slots=True)
class TopModelsResult:
    source: TopModelsSourceName
    cached: bool
    last_updated: datetime
    models: tuple[TopModel, ...]
    aliases: dict[str, str]


def top_model_to_api_dict(model: TopModel) -> dict[str, Any]:
    pricing: dict[str, Any] = {}
    if model.pricing.input_per_million is not None:
        pricing["input_per_million"] = model.pricing.input_per_million
    if model.pricing.output_per_million is not None:
        pricing["output_per_million"] = model.pricing.output_per_million
    if model.pricing.average_per_million is not None:
        pricing["average_per_million"] = model.pricing.average_per_million

    return {
        "id": model.id,
        "name": model.name,
        "provider": model.provider,
        "sub_provider": model.sub_provider,
        "context_window": model.context_window,
        "capabilities": list(model.capabilities),
        "pricing": pricing or None,
    }
