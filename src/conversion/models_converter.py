from __future__ import annotations

from typing import Any


def _extract_openai_models_list(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort extraction of OpenAI-style model list from a raw upstream payload."""
    data = raw.get("data")
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    return []


def raw_to_openai_models(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw upstream payload to OpenAI-style models list response."""
    return {
        "object": "list",
        "data": _extract_openai_models_list(raw),
    }


def raw_to_anthropic_models(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw upstream payload to Anthropic Models List schema.

    Anthropic schema (per docs):
    {
      "data": [{"id","created_at","display_name","type":"model"}, ...],
      "first_id": str | null,
      "last_id": str | null,
      "has_more": bool
    }

    We derive this from the upstream OpenAI-style list when available.
    """
    openai_models = _extract_openai_models_list(raw)

    data: list[dict[str, Any]] = []
    for m in openai_models:
        model_id = m.get("id")
        if not isinstance(model_id, str):
            continue

        display_name = m.get("display_name")
        if not isinstance(display_name, str):
            display_name = model_id

        created_at = m.get("created_at")
        # Many upstreams expose `created` (unix epoch seconds) instead.
        if not isinstance(created_at, str):
            created = m.get("created")
            created_at = str(created) if isinstance(created, int) else ""

        data.append(
            {
                "id": model_id,
                "type": "model",
                "display_name": display_name,
                "created_at": created_at,
            }
        )

    first_id = data[0]["id"] if data else None
    last_id = data[-1]["id"] if data else None

    return {
        "data": data,
        "first_id": first_id,
        "last_id": last_id,
        "has_more": False,
    }
