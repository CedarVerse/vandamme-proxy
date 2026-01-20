from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from src.core.config import Config
from src.core.dependencies import get_provider_resolver
from src.core.model_manager import ModelManager
from src.core.provider_config import ProviderConfig


@dataclass(frozen=True)
class ProviderContext:
    provider_name: str
    resolved_model: str
    provider_config: ProviderConfig
    client_api_key: str | None
    provider_api_key: str | None


async def resolve_provider_context(
    *, model: str, client_api_key: str | None, config: Config, model_manager: ModelManager
) -> ProviderContext:
    """Resolve provider/model and prepare auth context.

    - Resolves provider prefix + model aliasing via ModelManager
    - Fetches provider config
    - Enforces passthrough requirements
    - Selects initial provider API key for non-passthrough providers

    This is intentionally minimal: it returns the pieces endpoints need today.

    Args:
        model: The model name to resolve.
        client_api_key: The client's API key (for passthrough providers).
        config: The Config instance.
        model_manager: The ModelManager instance for model resolution.

    Returns:
        A ProviderContext with all resolved information.
    """

    provider_name, resolved_model = model_manager.resolve_model(model)

    provider_config = config.provider_manager.get_provider_config(provider_name)
    if provider_config is None:
        # Use ProviderResolver for consistent error messaging
        resolver = get_provider_resolver()
        available = config.provider_manager.list_providers()
        try:
            resolver.validate_provider_exists(provider_name, available)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from None
        # Should not reach here, but just in case
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    if provider_config.uses_passthrough and not client_api_key:
        raise HTTPException(
            status_code=401,
            detail=(
                f"Provider '{provider_name}' requires API key passthrough, "
                "but no client API key was provided"
            ),
        )

    provider_api_key: str | None = None
    if not provider_config.uses_passthrough:
        provider_api_key = await config.provider_manager.get_next_provider_api_key(provider_name)

    return ProviderContext(
        provider_name=provider_name,
        resolved_model=resolved_model,
        provider_config=provider_config,
        client_api_key=client_api_key,
        provider_api_key=provider_api_key,
    )
