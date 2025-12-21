import httpx
import pytest
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS


@pytest.mark.unit
def test_top_models_endpoint_manual_rankings_order(respx_mock, tmp_path, monkeypatch):
    """/top-models should follow TOML order, enriched via /v1/models provider=openrouter."""

    monkeypatch.setenv("TOP_MODELS_SOURCE", "manual_rankings")

    from src.core.config import Config

    Config.reset_singleton()

    from src.main import app

    rankings = tmp_path / "programming.toml"
    rankings.write_text(
        """version = 1
category = \"programming\"

[[models]]
id = \"google/gemini-2.0-flash\"

[[models]]
id = \"openai/gpt-4o\"
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("TOP_MODELS_RANKINGS_FILE", str(rankings))

    Config.reset_singleton()

    # Note: /v1/models fetches base_url/models. For provider=openrouter, base_url is configured
    # by ProviderManager; tests already mock the OpenRouter catalog endpoint directly.
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
        resp = client.get("/top-models?limit=10", headers=TEST_HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["object"] == "top_models"
    assert payload["source"] == "manual_rankings"

    # TOML order must be preserved
    assert [m["id"] for m in payload["models"]] == [
        "google/gemini-2.0-flash",
        "openai/gpt-4o",
    ]

    # Enrichment still comes from OpenRouter catalog parsing
    assert payload["models"][1]["provider"] == "openrouter"
    assert payload["models"][1]["sub_provider"] == "openai"
    assert payload["models"][1]["pricing"]["average_per_million"] == pytest.approx(6.25)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_top_models_exclude_env(tmp_path, monkeypatch):
    from src.top_models.service import TopModelsService, TopModelsServiceConfig

    rankings = tmp_path / "programming.toml"
    rankings.write_text(
        """version = 1
category = \"programming\"

[[models]]
id = \"openai/gpt-4o\"

[[models]]
id = \"google/gemini-2.0-flash\"
""",
        encoding="utf-8",
    )

    # Service-level config (avoid global env coupling)
    svc = TopModelsService(
        TopModelsServiceConfig(
            source="manual_rankings",
            rankings_file=rankings,
            timeout_seconds=5.0,
            exclude=("openai/",),
        )
    )

    async def fake_fetch_openai_models(*, provider: str, refresh: bool):
        assert provider == "openrouter"
        assert refresh is True
        return {
            "object": "list",
            "data": [
                {
                    "id": "openai/gpt-4o",
                    "context_length": 128000,
                    "pricing": {"prompt": 0.0000025, "completion": 0.00001},
                },
                {"id": "google/gemini-2.0-flash", "context_length": 1000000},
            ],
        }

    # Monkeypatch the service's source fetcher instead of doing HTTP mocking here.
    svc._source._fetch_openai_models = fake_fetch_openai_models  # type: ignore[attr-defined]

    result = await svc.get_top_models(limit=10, refresh=True, provider=None)

    ids = [m.id for m in result.models]
    assert "openai/gpt-4o" not in ids
    assert "google/gemini-2.0-flash" in ids


@pytest.mark.unit
def test_models_refresh_bypasses_cache(respx_mock):
    """/v1/models?refresh=true should skip cached response and refetch upstream."""

    from src.main import app

    def handler(_request):
        return httpx.Response(200, json={"data": [{"id": "m"}]})

    route = respx_mock.get("https://openrouter.ai/api/v1/models")
    route.mock(side_effect=handler)

    with TestClient(app) as client:
        r1 = client.get("/v1/models?provider=openrouter&format=raw", headers=TEST_HEADERS)
        r2 = client.get(
            "/v1/models?provider=openrouter&format=raw&refresh=true", headers=TEST_HEADERS
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert route.calls.call_count == 2
    assert r1.json()["data"][0]["id"] == "m"
    assert r2.json()["data"][0]["id"] == "m"
