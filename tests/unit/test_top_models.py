import httpx
import pytest
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS


@pytest.mark.unit
def test_top_models_endpoint_mocked(respx_mock):
    from src.main import app

    respx_mock.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "openai/gpt-4o",
                        "name": "GPT-4o",
                        "context_length": 128000,
                        "pricing": {"prompt": 0.0000025, "completion": 0.00001},
                        "capabilities": ["tools"],
                    },
                    {
                        "id": "google/gemini-2.0-flash",
                        "name": "Gemini Flash",
                        "context_length": 1000000,
                        "pricing": {"prompt": 0.0000005, "completion": 0.0000015},
                        "capabilities": ["tools", "vision"],
                    },
                ]
            },
        )
    )

    with TestClient(app) as client:
        resp = client.get("/top-models?limit=2", headers=TEST_HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["object"] == "top_models"
    assert payload["source"] == "openrouter"
    assert payload["models"][0]["id"] == "openai/gpt-4o"
    assert payload["models"][0]["provider"] == "openrouter"
    assert payload["models"][0]["sub_provider"] == "openai"
    assert payload["models"][0]["pricing"]["average_per_million"] == pytest.approx(6.25)
    assert "suggested_aliases" in payload
    assert payload["suggested_aliases"].get("top") == "openai/gpt-4o"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_top_models_exclude_env(respx_mock, tmp_path):
    from datetime import timedelta

    from src.top_models.service import TopModelsService, TopModelsServiceConfig

    svc = TopModelsService(
        TopModelsServiceConfig(
            source="openrouter",
            cache_dir=tmp_path,
            ttl=timedelta(days=1),
            timeout_seconds=5.0,
            exclude=("openai/",),
        )
    )

    respx_mock.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-4o", "context_length": 128000},
                    {"id": "google/gemini-2.0-flash", "context_length": 1000000},
                ]
            },
        )
    )

    result = await svc.get_top_models(limit=10, refresh=True, provider=None)

    ids = [m.id for m in result.models]
    assert "openai/gpt-4o" not in ids
    assert "google/gemini-2.0-flash" in ids
