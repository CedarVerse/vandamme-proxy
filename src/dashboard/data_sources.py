from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import yaml

logger = logging.getLogger(__name__)

# PyYAML is untyped; we rely on types-PyYAML in dev.


class DashboardConfigProtocol(Protocol):
    api_base_url: str


@dataclass(frozen=True)
class DashboardConfig(DashboardConfigProtocol):
    api_base_url: str = "http://localhost:8082"


class DashboardDataError(RuntimeError):
    pass


def _log_and_raise(msg: str, url: str, exc: Exception) -> None:
    logger.debug("%s (url=%s) - %s", msg, url, exc)
    raise DashboardDataError(f"{msg} from {url}: {exc}") from exc


async def fetch_health(*, cfg: DashboardConfigProtocol) -> dict[str, Any]:
    url = f"{cfg.api_base_url}/health"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    try:
        data = yaml.safe_load(resp.text)
    except Exception as e:  # noqa: BLE001
        _log_and_raise("Failed to parse YAML", url, e)

    if not isinstance(data, dict):
        raise DashboardDataError(f"Unexpected /health YAML shape from {url}: {type(data)}")
    return data


async def fetch_test_connection(*, cfg: DashboardConfigProtocol) -> dict[str, Any]:
    url = f"{cfg.api_base_url}/test-connection"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    # Endpoint returns JSON both on success and failure; preserve status.
    try:
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        _log_and_raise("Failed to parse JSON", url, e)

    if not isinstance(payload, dict):
        raise DashboardDataError(
            f"Unexpected /test-connection JSON shape from {url}: {type(payload)}"
        )

    payload["_http_status"] = resp.status_code
    return payload


async def fetch_running_totals(
    *,
    cfg: DashboardConfigProtocol,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    url = f"{cfg.api_base_url}/metrics/running-totals"
    params: dict[str, str] = {}
    if provider:
        params["provider"] = provider
    if model:
        params["model"] = model

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    try:
        data = yaml.safe_load(resp.text)
    except Exception as e:  # noqa: BLE001
        _log_and_raise("Failed to parse YAML", url, e)

    if not isinstance(data, dict):
        raise DashboardDataError(
            f"Unexpected /metrics/running-totals YAML shape from {url}: {type(data)}"
        )
    return data


async def fetch_models(
    *, cfg: DashboardConfigProtocol, provider: str | None = None
) -> dict[str, Any]:
    """Fetch available models from the API"""
    url = f"{cfg.api_base_url}/v1/models"
    params: dict[str, str] = {}
    headers: dict[str, str] = {}
    if provider:
        params["provider"] = provider
        headers["provider"] = provider

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)

    if resp.status_code != 200:
        raise DashboardDataError(f"Failed to fetch models from {url}: HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        _log_and_raise("Failed to parse JSON", url, e)

    if isinstance(data, dict):
        list_data = data.get("data")
        if isinstance(list_data, list):
            return data

        alt_list = data.get("models")
        if isinstance(alt_list, list):
            message_parts = [
                "dashboard.models: /v1/models returned dict with 'models' key",
                "instead of 'data'; wrapping",
            ]
            logger.warning(
                " ".join(message_parts),
                extra={"provider": provider or "", "count": len(alt_list)},
            )
            return {"object": "list", "data": alt_list}

        raise DashboardDataError(
            f"Unexpected /v1/models JSON shape from {url}: missing 'data' list"
        )

    if isinstance(data, list):
        logger.warning(
            "dashboard.models: /v1/models returned bare list; wrapping",
            extra={"provider": provider or "", "count": len(data)},
        )
        return {"object": "list", "data": data}

    raise DashboardDataError(f"Unexpected /v1/models JSON shape from {url}: {type(data)}")


async def fetch_aliases(*, cfg: DashboardConfigProtocol) -> dict[str, Any]:
    """Fetch model aliases from the API"""
    url = f"{cfg.api_base_url}/v1/aliases"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise DashboardDataError(f"Failed to fetch aliases from {url}: HTTP {resp.status_code}")

    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        _log_and_raise("Failed to parse JSON", url, e)

    if not isinstance(data, dict):
        raise DashboardDataError(f"Unexpected /v1/aliases JSON shape from {url}: {type(data)}")
    return data


async def fetch_all_providers(*, cfg: DashboardConfigProtocol) -> list[str]:
    """Extract list of all providers from health endpoint"""
    health_data = await fetch_health(cfg=cfg)
    providers = health_data.get("providers", {})
    return list(providers.keys())
