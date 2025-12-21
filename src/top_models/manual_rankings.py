from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.top_models.openrouter import openrouter_model_dict_to_top_model
from src.top_models.source import TopModelsSourceError
from src.top_models.types import TopModel


class OpenAIModelsFetcher(Protocol):
    async def __call__(self, *, provider: str, refresh: bool) -> dict[str, Any]: ...


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ManualRankingsConfig:
    rankings_file: Path


def _parse_rankings_toml(content: str) -> tuple[str, ...]:
    try:
        import tomli

        data = tomli.loads(content)
    except Exception as e:
        raise TopModelsSourceError(f"Failed to parse rankings TOML: {e}") from e

    models = data.get("models")
    if not isinstance(models, list):
        raise TopModelsSourceError("Rankings TOML missing [[models]] list")

    ids: list[str] = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if isinstance(model_id, str) and model_id:
            ids.append(model_id)

    if not ids:
        raise TopModelsSourceError("Rankings TOML contains no model IDs")

    return tuple(ids)


class ManualRankingsTopModelsSource:
    """Top-models source based on a human-maintained TOML ordering.

    Enrichment comes from OpenRouter's catalog as exposed via our own `/v1/models`
    endpoint (provider=openrouter, format=openai).
    """

    name = "manual_rankings"

    def __init__(
        self, *, cfg: ManualRankingsConfig, app_fetch_openai_models: OpenAIModelsFetcher
    ) -> None:
        self._cfg = cfg
        # Callable expected: async (provider: str, refresh: bool) -> dict
        # with {object: list, data: [...]}.
        self._fetch_openai_models = app_fetch_openai_models

    async def fetch_models(self, *, refresh: bool) -> tuple[TopModel, ...]:
        try:
            content = self._cfg.rankings_file.read_text(encoding="utf-8")
        except Exception as e:
            raise TopModelsSourceError(
                f"Failed to read rankings file: {self._cfg.rankings_file}: {e}"
            ) from e

        ranked_ids = _parse_rankings_toml(content)

        payload = await self._fetch_openai_models(provider="openrouter", refresh=refresh)
        if not isinstance(payload, dict):
            raise TopModelsSourceError("/v1/models did not return an object")

        data = payload.get("data")
        if not isinstance(data, list):
            raise TopModelsSourceError("/v1/models openai format missing 'data' list")

        # Build catalog map of id -> TopModel
        catalog: dict[str, TopModel] = {}
        for raw in data:
            if not isinstance(raw, dict):
                continue
            model = openrouter_model_dict_to_top_model(raw)
            if model is None:
                continue
            catalog[model.id] = model

        models: list[TopModel] = []
        for model_id in ranked_ids:
            m = catalog.get(model_id)
            if m is None:
                logger.info("Ranked model id not found in OpenRouter catalog: %s", model_id)
                continue
            models.append(m)

        return tuple(models)
