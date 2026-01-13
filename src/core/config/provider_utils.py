"""Provider-related utility functions.

This module provides helper functions for working with provider-specific
configuration, such as generating environment variable names and
getting default base URLs.

These utilities are used by the providers module and facade for
dynamic provider name handling.
"""


def get_provider_api_key_env_var(provider: str) -> str:
    """Get the environment variable name for a provider's API key.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        Environment variable name (e.g., "OPENAI_API_KEY")
    """
    return f"{provider.upper()}_API_KEY"


def get_provider_base_url_env_var(provider: str) -> str:
    """Get the environment variable name for a provider's base URL.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        Environment variable name (e.g., "OPENAI_BASE_URL")
    """
    return f"{provider.upper()}_BASE_URL"


def get_default_base_url(provider: str) -> str:
    """Get the default base URL for a provider.

    Args:
        provider: Provider name (e.g., "openai", "poe")

    Returns:
        Default base URL for the provider
    """
    provider_upper = provider.upper()
    if provider_upper == "OPENAI":
        return "https://api.openai.com/v1"
    elif provider_upper == "POE":
        return "https://api.poe.com/v1"
    return "https://api.openai.com/v1"
