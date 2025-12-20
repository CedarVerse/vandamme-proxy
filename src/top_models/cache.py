from __future__ import annotations

import datetime as dt
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.top_models.types import TopModel, TopModelPricing, TopModelsResult, TopModelsSourceName


class TopModelsCacheError(RuntimeError):
    pass


def _parse_iso8601(ts: str) -> datetime:
    # Accept both Z and +00:00 formats
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _to_iso8601_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _model_to_cache_dict(m: TopModel) -> dict[str, Any]:
    pricing: dict[str, Any] = {}
    if m.pricing.input_per_million is not None:
        pricing["input_per_million"] = m.pricing.input_per_million
    if m.pricing.output_per_million is not None:
        pricing["output_per_million"] = m.pricing.output_per_million

    return {
        "id": m.id,
        "name": m.name,
        "provider": m.provider,
        "context_window": m.context_window,
        "capabilities": list(m.capabilities),
        "pricing": pricing,
    }


def _model_from_cache_dict(d: dict[str, Any]) -> TopModel | None:
    model_id = d.get("id")
    if not isinstance(model_id, str) or not model_id:
        return None

    name = d.get("name") if isinstance(d.get("name"), str) else None
    provider = d.get("provider") if isinstance(d.get("provider"), str) else None

    context_window = d.get("context_window")
    if not isinstance(context_window, int):
        context_window = None

    caps = d.get("capabilities")
    capabilities: tuple[str, ...] = ()
    if isinstance(caps, list):
        capabilities = tuple(x for x in caps if isinstance(x, str))

    pricing_raw = d.get("pricing")
    pricing = TopModelPricing()
    if isinstance(pricing_raw, dict):
        ipm = pricing_raw.get("input_per_million")
        opm = pricing_raw.get("output_per_million")
        pricing = TopModelPricing(
            input_per_million=float(ipm) if isinstance(ipm, (int, float)) else None,
            output_per_million=float(opm) if isinstance(opm, (int, float)) else None,
        )

    return TopModel(
        id=model_id,
        name=name,
        provider=provider,
        context_window=context_window,
        capabilities=capabilities,
        pricing=pricing,
    )


class TopModelsDiskCache:
    def __init__(self, cache_dir: Path, ttl: timedelta) -> None:
        self._cache_dir = cache_dir
        self._ttl = ttl
        self._cache_file = cache_dir / "top-models.json"

    def read_if_fresh(self, expected_source: TopModelsSourceName) -> TopModelsResult | None:
        if not self._cache_file.exists():
            return None

        try:
            payload = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        if payload.get("schema_version") != 1:
            return None

        source = payload.get("source")
        if source != expected_source:
            return None

        last_updated_raw = payload.get("last_updated")
        if not isinstance(last_updated_raw, str):
            return None

        try:
            last_updated = _parse_iso8601(last_updated_raw)
        except Exception:
            return None

        if datetime.now(tz=dt.timezone.utc) - last_updated.astimezone(dt.timezone.utc) > self._ttl:
            return None

        models_raw = payload.get("models")
        if not isinstance(models_raw, list):
            return None

        models: list[TopModel] = []
        for item in models_raw:
            if not isinstance(item, dict):
                continue
            m = _model_from_cache_dict(item)
            if m is not None:
                models.append(m)

        aliases_raw = payload.get("aliases")
        aliases: dict[str, str] = {}
        if isinstance(aliases_raw, dict):
            for k, v in aliases_raw.items():
                if isinstance(k, str) and isinstance(v, str):
                    aliases[k] = v

        return TopModelsResult(
            source=expected_source,
            cached=True,
            last_updated=last_updated,
            models=tuple(models),
            aliases=aliases,
        )

    def write(
        self,
        *,
        source: TopModelsSourceName,
        last_updated: datetime,
        models: tuple[TopModel, ...],
        aliases: dict[str, str],
    ) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "schema_version": 1,
            "source": source,
            "last_updated": _to_iso8601_z(last_updated),
            "models": [_model_to_cache_dict(m) for m in models],
            "aliases": aliases,
        }

        tmp = self._cache_file.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self._cache_file)
        except Exception as e:
            raise TopModelsCacheError(f"Failed writing top-models cache: {e}") from e
