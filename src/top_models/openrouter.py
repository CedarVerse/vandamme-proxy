from __future__ import annotations

from typing import Any

import httpx

from src.top_models.source import TopModelsSourceConfig, TopModelsSourceError
from src.top_models.types import TopModel, TopModelPricing


class OpenRouterTopModelsSource:
    name = "openrouter"

    def __init__(self, config: TopModelsSourceConfig) -> None:
        self._config = config
        self._url = "https://openrouter.ai/api/v1/models"

    async def fetch_models(self) -> tuple[TopModel, ...]:
        headers = {
            "User-Agent": "vandamme-proxy/1.0",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                resp = await client.get(self._url, headers=headers)
                resp.raise_for_status()
                payload: dict[str, Any] = resp.json()  # type: ignore[assignment]
        except Exception as e:
            raise TopModelsSourceError(f"Failed to fetch OpenRouter models: {e}") from e

        data = payload.get("data")
        if not isinstance(data, list):
            raise TopModelsSourceError("OpenRouter models response missing 'data' list")

        models: list[TopModel] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue

            model_id = raw.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue

            name = raw.get("name") if isinstance(raw.get("name"), str) else None

            provider = None
            if "/" in model_id:
                provider = model_id.split("/", 1)[0]

            context_window = raw.get("context_length")
            if not isinstance(context_window, int):
                context_window = None

            capabilities: list[str] = []
            # OpenRouter's schema has varied over time; keep parsing resilient.
            for key in ("capabilities", "modalities", "tags"):
                v = raw.get(key)
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, str):
                            capabilities.append(item)

            pricing = TopModelPricing()
            pricing_raw = raw.get("pricing")
            if isinstance(pricing_raw, dict):
                prompt = pricing_raw.get("prompt")
                completion = pricing_raw.get("completion")
                # OpenRouter typically returns per-token USD.
                if isinstance(prompt, (int, float)):
                    pricing = TopModelPricing(
                        input_per_million=float(prompt) * 1_000_000,
                        output_per_million=pricing.output_per_million,
                    )
                if isinstance(completion, (int, float)):
                    pricing = TopModelPricing(
                        input_per_million=pricing.input_per_million,
                        output_per_million=float(completion) * 1_000_000,
                    )

            models.append(
                TopModel(
                    id=model_id,
                    name=name,
                    provider=provider,
                    context_window=context_window,
                    capabilities=tuple(dict.fromkeys(capabilities)),
                    pricing=pricing,
                )
            )

        return tuple(models)
