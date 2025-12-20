import httpx
import pytest
from fastapi.testclient import TestClient

from tests.config import TEST_HEADERS


@pytest.mark.unit
def test_aliases_endpoint_includes_suggested_overlay(respx_mock):
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
