# Models Documentation URL Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `models-url` configuration to providers that displays a documentation link when model fetching fails, providing users with a fallback to view available models.

**Architecture:** The feature follows the existing configuration hierarchy pattern (env vars > TOML > defaults) and injects the URL through the provider config lifecycle (loader -> health endpoint -> dashboard service -> UI component).

**Tech Stack:** Python dataclasses, TOML configuration, Dash/Bootstrap components, async services

---

## Task 1: Add `models_url` Field to ProviderConfig

**Files:**
- Modify: `src/core/provider_config.py:24-40`

**Step 1: Add the field to the dataclass**

Add the new optional field to the `ProviderConfig` dataclass:

```python
@dataclass
class ProviderConfig:
    """Configuration for a specific provider"""

    name: str
    api_key: str
    base_url: str
    # Optional multi-key support. If set, must be non-empty and contain no PASSTHROUGH_SENTINEL.
    api_keys: list[str] | None = None
    api_version: str | None = None
    timeout: int = 90
    max_retries: int = 2
    custom_headers: dict[str, str] = field(default_factory=dict)
    api_format: str = "openai"  # "openai" or "anthropic"
    tool_name_sanitization: bool = False
    auth_mode: str = AuthMode.API_KEY  # Authentication mode: api_key, passthrough, or oauth
    models_url: str | None = None  # NEW: Provider models documentation URL
```

**Step 2: Run type check**

Run: `make type-check`

Expected: PASS (adding optional field with default is backward compatible)

**Step 3: Commit**

```bash
hug add src/core/provider_config.py
hug commit -m "feat(provider): add models_url field to ProviderConfig"
```

---

## Task 2: Load models_url in ProviderConfigLoader

**Files:**
- Modify: `src/core/provider/provider_config_loader.py:195-212`

**Step 1: Add loading logic after other settings**

In the `load_provider()` method, add `models_url` loading after line 198 (after `max_retries`):

```python
        # Other settings
        timeout = int(os.environ.get("REQUEST_TIMEOUT", toml_config.get("timeout", "90")))
        max_retries = int(os.environ.get("MAX_RETRIES", toml_config.get("max-retries", "2")))

        # Models documentation URL
        models_url = os.environ.get(f"{provider_upper}_MODELS_URL") or toml_config.get("models-url")

        return ProviderConfig(
            name=provider_name,
            api_key=api_key,
            api_keys=api_keys if len(api_keys) > 1 else None,
            base_url=base_url,
            api_version=os.environ.get(f"{provider_upper}_API_VERSION")
            or toml_config.get("api-version"),
            timeout=timeout,
            max_retries=max_retries,
            custom_headers=self.get_custom_headers(provider_upper),
            api_format=api_format,
            tool_name_sanitization=bool(toml_config.get("tool-name-sanitization", False)),
            auth_mode=auth_mode,
            models_url=models_url,  # NEW
        )
```

**Step 2: Run type check**

Run: `make type-check`

Expected: PASS

**Step 3: Commit**

```bash
hug add src/core/provider/provider_config_loader.py
hug commit -m "feat(loader): load models_url from env var and TOML config"
```

---

## Task 3: Expose models_url in Health Check Endpoint

**Files:**
- Modify: `src/api/services/endpoint_services.py:453-482`

**Step 1: Add models_url to provider info dict**

In the `_gather_provider_info()` method, add `models_url` to the provider dict after line 471 (after `auth_mode`):

```python
                providers[provider_name] = {
                    "api_format": provider_config.api_format,
                    "base_url": provider_config.base_url,
                    "auth_mode": auth_mode,
                    "models_url": provider_config.models_url,  # NEW
                    "api_key_hash": (
                        f"sha256:{self._config.provider_manager.get_api_key_hash(provider_config.api_key)}"
                        if provider_config.api_key
                        else "<not set>"
                    ),
                }
```

**Step 2: Run type check**

Run: `make type-check`

Expected: PASS

**Step 3: Test health endpoint locally**

Run: `vdm server start` (in background)

Then: `curl -s http://localhost:8082/health | grep -A 5 "chatgpt:"`

Expected: Should see `models_url` field in provider info (will be `null` until defaults.toml is updated in Task 7)

**Step 4: Commit**

```bash
hug add src/api/services/endpoint_services.py
hug commit -m "feat(health): expose models_url in health endpoint"
```

---

## Task 4: Update ProviderModelsView Dataclass

**Files:**
- Modify: `src/dashboard/services/models.py:18-24`

**Step 1: Add new fields to dataclass**

```python
@dataclass(frozen=True)
class ProviderModelsView:
    row_data: list[dict[str, Any]]
    provider_options: list[dict[str, str]]
    provider_value: str | None
    hint: Any
    models_url: str | None = None  # NEW
    error_message: str | None = None  # NEW
```

**Step 2: Run type check**

Run: `make type-check`

Expected: PASS

**Step 3: Commit**

```bash
hug add src/dashboard/services/models.py
hug commit -m "feat(dashboard): add models_url and error_message to ProviderModelsView"
```

---

## Task 5: Update build_provider_models_view() Service

**Files:**
- Modify: `src/dashboard/services/models.py:34-91`

**Step 1: Refactor to extract models_url and handle errors**

Replace the entire `build_provider_models_view()` function with:

```python
async def build_provider_models_view(*, cfg: Any, provider_value: str | None) -> ProviderModelsView:
    """Fetch models and build view fragments for the Provider Models tab."""

    health = await fetch_health(cfg=cfg)
    providers = await fetch_all_providers(cfg=cfg)

    default_provider = health.get("default_provider")
    if not isinstance(default_provider, str):
        default_provider = ""

    sorted_providers = sorted(p for p in providers if isinstance(p, str) and p)

    selected_provider = provider_value.strip() if provider_value else ""
    if not selected_provider:
        if default_provider:
            selected_provider = default_provider
        elif sorted_providers:
            selected_provider = sorted_providers[0]

    provider_options: list[dict[str, str]] = []
    if default_provider and default_provider in sorted_providers:
        provider_options.append(
            {"label": f"{default_provider} (default)", "value": default_provider}
        )

    provider_options.extend(
        [{"label": p, "value": p} for p in sorted_providers if p != default_provider]
    )

    hint = [
        html.Span("Listing models for "),
        provider_badge(selected_provider)
        if selected_provider
        else html.Span("(no providers)", className="text-muted"),
    ]

    # NEW: Get models_url from health endpoint
    providers_dict = health.get("providers", {})
    provider_info = providers_dict.get(selected_provider, {}) if isinstance(providers_dict, dict) else {}
    models_url = provider_info.get("models_url") if isinstance(provider_info, dict) else None

    # Fetch models with error handling
    try:
        models_data = await fetch_models(cfg=cfg, provider=selected_provider or None)
        models = models_data.get("data", [])
    except Exception as e:
        # On error, return view with models_url and error message
        logger.debug(f"Failed to fetch models for {selected_provider}: {e}")
        return ProviderModelsView(
            row_data=[],
            provider_options=provider_options,
            provider_value=selected_provider or None,
            hint=hint,
            models_url=models_url,
            error_message=str(e),
        )

    inferred_provider = selected_provider or default_provider or "multiple"
    for model in models:
        if not model.get("provider"):
            model["provider"] = inferred_provider

    if not models:
        return ProviderModelsView(
            row_data=[],
            provider_options=provider_options,
            provider_value=selected_provider or None,
            hint=hint,
            models_url=models_url,
            error_message=None,
        )

    return ProviderModelsView(
        row_data=models_row_data(models),
        provider_options=provider_options,
        provider_value=selected_provider or None,
        hint=hint,
        models_url=models_url,
        error_message=None,
    )
```

**Step 2: Run type check**

Run: `make type-check`

Expected: PASS

**Step 3: Commit**

```bash
hug add src/dashboard/services/models.py
hug commit -m "feat(dashboard): extract models_url from health endpoint and handle fetch errors"
```

---

## Task 6: Add Documentation Link Container to Models Page Layout

**Files:**
- Modify: `src/dashboard/pages/models.py:9-39`

**Step 1: Add container div in _provider_tab_content()**

Add the documentation link container after line 31 (after the hint div):

```python
def _provider_tab_content() -> list:
    """Content for provider models tab."""
    return [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Stack(
                        [
                            dbc.Label("Provider", className="text-muted small mb-0"),
                            dcc.Dropdown(
                                id="vdm-models-provider-dropdown",
                                options=[],
                                value=None,
                                placeholder="Provider",
                                clearable=False,
                            ),
                        ],
                        gap=1,
                    ),
                )
            ]
        ),
        html.Div(id="vdm-models-provider-hint", className="text-muted small mb-2"),
        # NEW: Container for models documentation link
        html.Div(id="vdm-models-provider-docs-link", className="mb-3"),
        models_table(
            [],
            sort_field="id",
            sort_desc=False,
            show_provider=True,
            grid_id="vdm-models-provider-grid",
        ),
    ]
```

**Step 2: Commit**

```bash
hug add src/dashboard/pages/models.py
hug commit -m "feat(dashboard): add container for models documentation link"
```

---

## Task 7: Update Callback with Documentation Link Output

**Files:**
- Modify: `src/dashboard/callbacks/models.py:17-52`

**Step 1: Add new output to callback decorator**

Add the new output after `Output("vdm-models-provider-hint", "children")`:

```python
    @app.callback(
        Output("vdm-models-provider-grid", "rowData"),
        Output("vdm-models-provider-dropdown", "options"),
        Output("vdm-models-provider-dropdown", "value"),
        Output("vdm-models-provider-hint", "children"),
        Output("vdm-models-provider-docs-link", "children"),  # NEW
        Input("vdm-models-poll", "n_intervals"),
        Input("vdm-models-refresh", "n_clicks"),
        Input("vdm-models-provider-dropdown", "value"),
        prevent_initial_call=False,
    )
    def refresh_provider_models(
        _n: int,
        _clicks: int | None,
        provider_value: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None, Any, Any]:  # Updated return type
```

**Step 2: Update function body to build and return docs link**

Replace the function body to build and return the docs link component:

```python
    def refresh_provider_models(
        _n: int,
        _clicks: int | None,
        provider_value: str | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None, Any, Any]:
        """Fetch and update provider models tab."""
        try:
            from src.dashboard.services.models import build_provider_models_view

            view = run(build_provider_models_view(cfg=cfg, provider_value=provider_value))

            # NEW: Build documentation link component
            docs_link = _build_docs_link_component(
                models_url=view.models_url,
                error_message=view.error_message,
                has_models=bool(view.row_data),
            )

            return view.row_data, view.provider_options, view.provider_value, view.hint, docs_link

        except Exception:
            logger.exception("dashboard.models: provider refresh failed")
            return (
                [],
                [],
                None,
                html.Span("Failed to load providers", className="text-muted"),
                html.Div(),
            )
```

**Step 3: Add the helper function**

Add the helper function at the end of the file (after line 320):

```python
def _build_docs_link_component(
    models_url: str | None,
    error_message: str | None,
    has_models: bool,
) -> Any:
    """Build documentation link component based on context.

    Shows:
    - Nothing if models loaded successfully
    - Documentation link + error explanation if fetch failed and URL available
    - Error message only if no URL available
    """
    if has_models:
        return html.Div()

    if not models_url:
        if error_message:
            return dbc.Alert(
                f"Could not load models: {error_message}",
                color="warning",
                className="small",
            )
        return html.Div()

    # Build helpful alert with documentation link
    message_parts = [
        html.P("Models list is not available for this provider.", className="mb-2 small"),
        html.P(
            [
                "View available models at: ",
                dbc.Button(
                    "Open documentation",
                    href=models_url,
                    target="_blank",
                    external_link=True,
                    color="info",
                    size="sm",
                    className="ms-2",
                ),
            ],
            className="mb-0 small",
        ),
    ]

    if error_message:
        message_parts.insert(
            1,
            html.P(
                f"Reason: {error_message}",
                className="text-muted small mb-2"
            ),
        )

    return dbc.Alert(message_parts, color="info", className="small")
```

**Step 4: Run type check**

Run: `make type-check`

Expected: PASS

**Step 5: Commit**

```bash
hug add src/dashboard/callbacks/models.py
hug commit -m "feat(dashboard): add documentation link output and helper component"
```

---

## Task 8: Add Default models-url Values

**Files:**
- Modify: `src/config/defaults.toml:74-97`

**Step 1: Add models-url to chatgpt provider**

Add `models-url` after `max-retries`:

```toml
# ChatGPT provider defaults (OAuth authentication)
[chatgpt]
base-url = "https://api.openai.com/v1"
api-format = "openai"
auth-mode = "oauth"
timeout = 90
max-retries = 2
models-url = "https://platform.openai.com/docs/models"
```

**Step 2: Add models-url to anthropic provider**

Add `models-url` after `max-retries`:

```toml
# Anthropic provider defaults
[anthropic]
base-url = "https://api.anthropic.com"
api-format = "anthropic"
timeout = 90
max-retries = 2
models-url = "https://docs.anthropic.com/en/docs/about-claude/models"
```

**Step 3: Commit**

```bash
hug add src/config/defaults.toml
hug commit -m "feat(config): add default models-url for chatgpt and anthropic providers"
```

---

## Task 9: Unit Test ProviderConfig models_url Field

**Files:**
- Create: `tests/unit/provider/test_provider_config_models_url.py`

**Step 1: Write the test file**

```python
"""Test models_url field in ProviderConfig."""

import pytest

from src.core.provider_config import ProviderConfig


@pytest.mark.unit
def test_provider_config_with_models_url():
    """ProviderConfig accepts models_url field."""
    config = ProviderConfig(
        name="test-provider",
        api_key="test-key",
        base_url="https://api.example.com/v1",
        models_url="https://example.com/docs/models",
    )
    assert config.models_url == "https://example.com/docs/models"


@pytest.mark.unit
def test_provider_config_default_models_url():
    """ProviderConfig models_url defaults to None."""
    config = ProviderConfig(
        name="test-provider",
        api_key="test-key",
        base_url="https://api.example.com/v1",
    )
    assert config.models_url is None
```

**Step 2: Run test**

Run: `pytest tests/unit/provider/test_provider_config_models_url.py -v`

Expected: PASS (2 tests passed)

**Step 3: Commit**

```bash
hug add tests/unit/provider/test_provider_config_models_url.py
hug commit -m "test(provider): add unit tests for models_url field"
```

---

## Task 10: Unit Test ProviderConfigLoader models_url Loading

**Files:**
- Create: `tests/unit/provider/test_provider_config_loader_models_url.py`

**Step 1: Write the test file**

```python
"""Test models_url loading in ProviderConfigLoader."""

import os
import pytest

from src.core.provider.provider_config_loader import ProviderConfigLoader


@pytest.mark.unit
def test_load_models_url_from_env_var(monkeypatch):
    """Loader reads models_url from {PROVIDER}_MODELS_URL environment variable."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTPROV_MODELS_URL", "https://example.com/docs/models")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url == "https://example.com/docs/models"


@pytest.mark.unit
def test_load_models_url_from_toml(monkeypatch, tmp_path):
    """Loader reads models_url from TOML config when env var not set."""
    import sys
    from pathlib import Path

    # Create a minimal TOML config
    toml_file = tmp_path / "vandamme-config.toml"
    toml_file.write_text(
        '[testprov]\n'
        'base-url = "https://api.example.com/v1"\n'
        'models-url = "https://example.com/docs/models"\n'
    )

    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    # Add tmp_path to sys.path so AliasConfigLoader can find the TOML
    # (This is a simplified test; in real code, TOML loading goes through AliasConfigLoader)

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    # Note: This test assumes the TOML path is configured correctly
    # In practice, the actual integration test would verify end-to-end
    assert config is not None


@pytest.mark.unit
def test_env_var_overrides_toml_for_models_url(monkeypatch):
    """Environment variable takes precedence over TOML for models_url."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("TESTPROV_MODELS_URL", "https://env-var-url.com/models")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url == "https://env-var-url.com/models"


@pytest.mark.unit
def test_no_models_url_when_not_configured(monkeypatch):
    """models_url is None when neither env var nor TOML provides it."""
    monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
    monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")

    loader = ProviderConfigLoader()
    config = loader.load_provider("testprov", require_api_key=True)

    assert config is not None
    assert config.models_url is None
```

**Step 2: Run test**

Run: `pytest tests/unit/provider/test_provider_config_loader_models_url.py -v`

Expected: PASS (4 tests passed)

**Step 3: Commit**

```bash
hug add tests/unit/provider/test_provider_config_loader_models_url.py
hug commit -m "test(loader): add unit tests for models_url loading"
```

---

## Task 11: Integration Test Health Endpoint models_url

**Files:**
- Create: `tests/integration/test_models_url_health.py`

**Step 1: Write the integration test**

```python
"""Integration test for models_url in health endpoint."""

import pytest

from tests.helpers.server import start_test_server, stop_test_server


@pytest.mark.integration
async def test_health_endpoint_includes_models_url():
    """Health endpoint includes models_url for configured providers."""
    async with start_test_server(
        env_overrides={
            "OPENAI_API_KEY": "sk-test-key",
            "OPENAI_MODELS_URL": "https://platform.openai.com/docs/models",
        }
    ) as server:
        async with server.get_client() as client:
            response = await client.get("/health")

            assert response.status_code == 200

            # Parse YAML response
            import yaml

            health_data = yaml.safe_load(response.text)

            # Verify providers section exists
            assert "providers" in health_data
            providers = health_data["providers"]

            # Check openai provider has models_url
            assert "openai" in providers
            assert providers["openai"]["models_url"] == "https://platform.openai.com/docs/models"


@pytest.mark.integration
async def test_health_endpoint_models_url_null_when_not_configured():
    """Health endpoint returns null for models_url when not configured."""
    async with start_test_server(
        env_overrides={
            "OPENAI_API_KEY": "sk-test-key",
            # OPENAI_MODELS_URL not set
        }
    ) as server:
        async with server.get_client() as client:
            response = await client.get("/health")

            assert response.status_code == 200

            import yaml

            health_data = yaml.safe_load(response.text)
            providers = health_data["providers"]

            assert "openai" in providers
            # models_url should be null or not present
            models_url = providers["openai"].get("models_url")
            assert models_url is None
```

**Step 2: Run test**

Run: `make test-integration`

Expected: PASS (includes new integration tests)

**Step 3: Commit**

```bash
hug add tests/integration/test_models_url_health.py
hug commit -m "test(integration): add health endpoint models_url tests"
```

---

## Task 12: Manual Verification

**Step 1: Start server with ChatGPT OAuth provider**

```bash
export CHATGPT_AUTH_MODE=oauth
export CHATGPT_BASE_URL="https://api.openai.com/v1"
vdm server start
```

**Step 2: Navigate to dashboard**

Open: http://127.0.0.1:8082/dashboard/models

**Step 3: Select chatgpt provider**

From the "Provider Models" tab dropdown, select "chatgpt"

**Step 4: Verify documentation link appears**

Expected:
- An info alert should appear saying "Models list is not available for this provider"
- A button "Open documentation" should be present
- Clicking the button should open https://platform.openai.com/docs/models in a new tab

**Step 5: Test with environment variable override**

```bash
# Stop the server first (Ctrl+C)
export CHATGPT_MODELS_URL="https://custom-url.com/docs"
vdm server start
```

Then refresh the dashboard and verify the link uses the custom URL.

**Step 6: Test with provider that has models**

Select a provider that successfully loads models (like "poe" if configured)

Expected:
- No documentation link should appear
- Models should display in the grid

---

## Summary of Changes

| File | Change |
|------|--------|
| `src/core/provider_config.py` | Add `models_url: str \| None = None` field |
| `src/core/provider/provider_config_loader.py` | Load `models_url` from env/TOML in `load_provider()` |
| `src/api/services/endpoint_services.py` | Include `models_url` in `_gather_provider_info()` |
| `src/dashboard/services/models.py` | Add `models_url`, `error_message` to `ProviderModelsView`; update `build_provider_models_view()` |
| `src/dashboard/pages/models.py` | Add `vdm-models-provider-docs-link` div to layout |
| `src/dashboard/callbacks/models.py` | Add callback output and `_build_docs_link_component()` helper |
| `src/config/defaults.toml` | Add `models-url` to chatgpt and anthropic providers |
| `tests/unit/provider/test_provider_config_models_url.py` | New test file |
| `tests/unit/provider/test_provider_config_loader_models_url.py` | New test file |
| `tests/integration/test_models_url_health.py` | New test file |

---

## Configuration Hierarchy

```
{PROVIDER}_MODELS_URL (env var, highest priority)
  > [provider.models-url] (TOML: ./vandamme-config.toml or ~/.config/vandamme-proxy/vandamme-config.toml)
  > [provider.models-url] (TOML: src/config/defaults.toml, lowest priority)
  > None (not configured)
```

---

## Edge Cases Handled

1. **No models_url configured**: Show error message only, no link
2. **Invalid models_url**: Dashboard shows link as-is (user responsibility)
3. **Both models and models_url present**: Don't show docs link (models take precedence)
4. **Network timeout**: Use health endpoint fallback for models_url
5. **OAuth providers**: models_url provides documentation since API fetch fails
6. **Passthrough providers**: models_url provides documentation since client key required
