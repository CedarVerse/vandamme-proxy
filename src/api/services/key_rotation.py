from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException

from src.core.config import Config
from src.core.provider_config import ProviderConfig

NextApiKey = Callable[[set[str]], Awaitable[str]]


def make_next_provider_key_fn(*, provider_name: str, config: Config) -> NextApiKey:
    """Create a reusable provider API key rotator.

    Providers may be configured with multiple API keys. Upstream calls can "exclude" keys
    that have failed (e.g. 401/403/429) and ask for the next viable key.

    This helper centralizes the repeated logic previously in src/api/endpoints.py.

    Fetches api_keys dynamically from provider config at runtime to ensure the callback
    always sees the current configuration, even if the provider config is modified.

    Args:
        provider_name: Name of the provider.
        config: The Config instance.

    Returns:
        An async function that returns the next available API key.
    """

    async def _next_provider_key(exclude: set[str]) -> str:
        # Fetch provider config fresh to get current api_keys
        try:
            provider_config = config.provider_manager.get_provider_config(provider_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from None

        api_keys = provider_config.get_api_keys()

        if len(exclude) >= len(api_keys):
            raise HTTPException(status_code=429, detail="All provider API keys exhausted")

        while True:
            k = await config.provider_manager.get_next_provider_api_key(provider_name)
            if k not in exclude:
                return k

    return _next_provider_key


def build_api_key_params(
    *,
    provider_config: ProviderConfig | None,
    provider_name: str,
    client_api_key: str | None,
    provider_api_key: str | None,
    config: Config,
) -> dict[str, Any]:
    """Build api_key and next_api_key parameters for upstream calls.

    Centralizes the 4x duplicated pattern in create_message().

    Args:
        provider_config: The provider configuration (may be None).
        provider_name: Name of the provider (for key rotation).
        client_api_key: The client's API key (for passthrough providers).
        provider_api_key: The provider's API key (for non-passthrough providers).
        config: The Config instance.

    Returns:
        A dict with 'api_key' and 'next_api_key' keys suitable for unpacking
        into client method calls.
    """
    if provider_config and provider_config.uses_passthrough:
        return {"api_key": client_api_key, "next_api_key": None}

    return {
        "api_key": provider_api_key,
        "next_api_key": (
            make_next_provider_key_fn(provider_name=provider_name, config=config)
            if provider_config
            else None
        ),
    }
