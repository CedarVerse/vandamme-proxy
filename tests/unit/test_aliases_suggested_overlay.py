import httpx
import pytest
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS


@pytest.mark.unit
def test_aliases_endpoint_includes_suggested_overlay(respx_mock, tmp_path, monkeypatch):
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

    monkeypatch.setenv("TOP_MODELS_SOURCE", "manual_rankings")
    monkeypatch.setenv("TOP_MODELS_RANKINGS_FILE", str(rankings))

    from src.core.config import Config

    Config.reset_singleton()

    from src.main import app

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

    with TestClient(app) as client:
        resp = client.get("/v1/aliases", headers=TEST_HEADERS)

    assert resp.status_code == 200
    payload = resp.json()

    assert "aliases" in payload
    assert "suggested" in payload
    assert "default" in payload["suggested"]
    assert payload["suggested"]["default"].get("top") == "openai/gpt-4o"
