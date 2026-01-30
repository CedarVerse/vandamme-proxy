from __future__ import annotations

import httpx
import pytest

from src.dashboard.components.ag_grid import models_ag_grid
from src.dashboard.data_sources import DashboardConfig, fetch_models


class _DummyResponse:
    def __init__(self, status_code: int, json_payload: object):
        self.status_code = status_code
        self._json_payload = json_payload

    def json(self):
        return self._json_payload


@pytest.mark.asyncio
async def test_fetch_models_requests_openai_format(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = DashboardConfig(api_base_url="http://example")

    captured: dict[str, object] = {}

    async def fake_get(self, url: str, params=None, headers=None):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _DummyResponse(status_code=200, json_payload={"object": "list", "data": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    await fetch_models(cfg=cfg, provider=None)

    assert captured["url"] == "http://example/v1/models"
    assert isinstance(captured["params"], dict)
    assert captured["params"].get("format") == "openai"


@pytest.mark.parametrize(
    ("model_patch", "expected_url"),
    [
        # OpenAI-style nested metadata.
        (
            {"metadata": {"image": {"url": "https://example.com/icon.jpeg"}}},
            "https://example.com/icon.jpeg",
        ),
        # Flattened metadata variants.
        (
            {"metadata": {"image_url": "https://example.com/icon-flat.jpeg"}},
            "https://example.com/icon-flat.jpeg",
        ),
        (
            {"metadata": {"image": "https://example.com/icon-str.jpeg"}},
            "https://example.com/icon-str.jpeg",
        ),
        (
            {"metadata": {"icon": {"url": "https://example.com/icon-alt.jpeg"}}},
            "https://example.com/icon-alt.jpeg",
        ),
        # Top-level fallback.
        ({"image_url": "https://example.com/icon-top.jpeg"}, "https://example.com/icon-top.jpeg"),
    ],
)
def test_models_ag_grid_extracts_model_icon_url_variants(
    model_patch: dict[str, object],
    expected_url: str,
) -> None:
    models = [
        {
            "id": "Claude-Sonnet-4.5",
            "created": 1758868894776,
            "description": "Claude Sonnet 4.5 represents a major leap forward...",
            "owned_by": "Anthropic",
            "architecture": {"modality": "text,image->text"},
            "context_window": {"context_length": 128000, "max_output_tokens": 16384},
            "pricing": {"prompt": "0.0000026", "completion": "0.000013"},
            **model_patch,
        }
    ]

    grid = models_ag_grid(models)
    row = grid.rowData[0]

    assert row["owned_by"] == "Anthropic"
    assert row["architecture_modality"] == "text,image->text"
    assert row["description_full"].startswith("Claude Sonnet")
    assert row["description_preview"].startswith("Claude Sonnet")
    assert row["description_preview"].endswith("...")

    assert row["context_length"] == 128000
    assert row["max_output_tokens"] == 16384

    assert row["model_icon_url"] == expected_url

    # pricing is in USD/token; table shows USD per million tokens
    assert row["pricing_prompt_per_million"] == "2.60"
    assert row["pricing_completion_per_million"] == "13.00"

    # created is in ms; should be normalized to seconds as int
    assert isinstance(row["created"], int)
    assert row["created"] == 1758868894


def test_models_ag_grid_rejects_unsafe_icon_urls() -> None:
    models = [
        {
            "id": "Claude-Sonnet-4.5",
            "created": 1758868894776,
            "owned_by": "Anthropic",
            "metadata": {"image": {"url": "javascript:alert(1)"}},
        }
    ]

    grid = models_ag_grid(models)
    row = grid.rowData[0]

    assert row["model_icon_url"] is None
    # Ensure we still render the row and ID.
    assert row["id"] == "Claude-Sonnet-4.5"


def test_models_ag_grid_uses_registered_model_id_renderer() -> None:
    grid = models_ag_grid([])

    # Dash components store props in .to_plotly_json()
    props = grid.to_plotly_json()["props"]
    col_defs = props["columnDefs"]

    model_id_col = next(c for c in col_defs if c.get("field") == "id")
    assert model_id_col["cellRenderer"] == "vdmModelIdWithIconRenderer"
    # Copy-to-clipboard is handled by a JS listener attached to the grid API.
    assert model_id_col["cellStyle"]["cursor"] == "copy"


def test_models_ag_grid_provider_column_label_is_correct() -> None:
    """Test that the provider column is labeled 'Provider' not 'Sub-Provider'."""
    grid = models_ag_grid([])

    # Dash components store props in .to_plotly_json()
    props = grid.to_plotly_json()["props"]
    col_defs = props["columnDefs"]

    provider_col = next(c for c in col_defs if c.get("field") == "owned_by")
    assert provider_col["headerName"] == "Provider"
    # Should not be 'Sub-Provider' which is misleading for profile models
    assert provider_col["headerName"] != "Sub-Provider"


def test_models_ag_grid_created_column_has_value_getter_for_profile_models() -> None:
    """Test that the Created column has a valueGetter to hide dates for profile models."""
    grid = models_ag_grid([])

    # Dash components store props in .to_plotly_json()
    props = grid.to_plotly_json()["props"]
    col_defs = props["columnDefs"]

    created_col = next(c for c in col_defs if c.get("field") == "created_iso")
    # Should have a valueGetter that returns null for profile models
    assert "valueGetter" in created_col
    assert (
        created_col["valueGetter"]["function"]
        == "params.data.is_profile_model ? null : params.data.created_iso"
    )


def test_models_ag_grid_profile_model_row_data_includes_is_profile_model() -> None:
    """Test that profile model rows include the is_profile_model field."""
    models = [
        {
            "id": "haiku",
            "created": 1758868894776,
            "owned_by": "main",
            "is_profile_model": True,
            "resolution_chain": ["haiku", "anthropic:claude-3-5-haiku-20241022"],
            "final_model_id": "anthropic:claude-3-5-haiku-20241022",
            "data_source": "local",
        }
    ]

    grid = models_ag_grid(models)
    row = grid.rowData[0]

    # Profile model fields should be present
    assert row["is_profile_model"] is True
    assert row["resolution_chain"] == ["haiku", "anthropic:claude-3-5-haiku-20241022"]
    assert row["final_model_id"] == "anthropic:claude-3-5-haiku-20241022"
    assert row["data_source"] == "local"


def test_models_ag_grid_regular_model_row_data_has_is_profile_model_false() -> None:
    """Test that regular model rows have is_profile_model set to False."""
    models = [
        {
            "id": "claude-3-5-sonnet-20241022",
            "created": 1758868894776,
            "owned_by": "Anthropic",
            "description": "Claude 3.5 Sonnet",
        }
    ]

    grid = models_ag_grid(models)
    row = grid.rowData[0]

    # Regular models should have is_profile_model=False
    assert row["is_profile_model"] is False
    # Profile-specific fields should be None or empty
    assert row.get("resolution_chain") == []
    assert row.get("final_model_id") is None
    assert row.get("data_source") is None
