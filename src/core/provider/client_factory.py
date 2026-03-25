"""Client factory for creating and caching API client instances."""

from pathlib import Path
from typing import TYPE_CHECKING, Union

from src.core.client import OpenAIClient
from src.core.provider_config import ProviderConfig

# Type ignore for local oauth module which doesn't have py.typed marker
try:
    from src.core.oauth.storage import FileSystemAuthStorage  # type: ignore[import-untyped]
    from src.core.oauth.tokens import TokenManager  # type: ignore[import-untyped]
except ImportError:
    TokenManager = None  # type: ignore[assignment, misc]
    FileSystemAuthStorage = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from src.core.anthropic_client import AnthropicClient
    from src.core.responses_client import ResponsesAPIClient


class ClientFactory:
    """Creates and caches API client instances per provider.

    Responsibilities:
    - Create OpenAI/Anthropic/ResponsesAPI clients based on api_format
    - Cache clients per provider
    - Handle passthrough mode (no API key in client)

    Clients are cached to avoid creating new HTTP connections for each request.

    Client type selection by api_format:
      "responses"  → ResponsesAPIClient (httpx, internal ChatGPT Responses API)
      "anthropic"  → AnthropicClient    (httpx, Anthropic-compatible passthrough)
      "openai"     → OpenAIClient       (OpenAI SDK, default)
    """

    def __init__(self) -> None:
        """Initialize a new client factory."""
        self._clients: dict[str, OpenAIClient | AnthropicClient | ResponsesAPIClient] = {}

    def get_or_create_client(
        self, config: ProviderConfig
    ) -> Union[OpenAIClient, "AnthropicClient", "ResponsesAPIClient"]:
        """Get cached client or create new one for the provider config.

        Args:
            config: The provider configuration.

        Returns:
            A cached or newly created client instance.
        """
        cache_key = config.name

        if cache_key not in self._clients:
            # For passthrough providers, pass None as API key
            api_key_for_init = None if config.uses_passthrough else config.api_key

            # For OAuth providers, create TokenManager with per-provider storage
            oauth_token_manager = None
            if config.uses_oauth:
                if TokenManager is None or FileSystemAuthStorage is None:
                    raise ImportError(
                        "oauth is required for OAuth providers. "
                        "Please ensure the dependency is installed."
                    )
                # Create per-provider storage path: ~/.vandamme/oauth/{provider}/
                storage_path = Path.home() / ".vandamme" / "oauth" / config.name
                storage = FileSystemAuthStorage(base_path=storage_path)
                oauth_token_manager = TokenManager(
                    storage=storage,
                    raise_on_refresh_failure=False,
                )

            # Three-way dispatch: responses → anthropic → openai (default)
            if config.is_responses_format:
                from src.core.responses_client import ResponsesAPIClient

                # ResponsesAPIClient uses httpx directly (not the OpenAI SDK) because
                # the internal ChatGPT Responses API endpoint (/v1/responses) is not
                # supported by any public SDK.  It requires OAuth tokens and specific
                # headers that differ from both OpenAI and Anthropic auth flows.
                #
                # NOTE: api_key_for_init is intentionally NOT passed here.  The
                # Responses API is OAuth-only; there is no fallback to static API keys.
                # If oauth_token_manager is None, stream_responses() will raise a
                # clear ValueError on first use, prompting the user to run
                # 'vdm oauth login <provider>'.
                self._clients[cache_key] = ResponsesAPIClient(
                    base_url=config.base_url,
                    timeout=config.timeout,
                    custom_headers=config.custom_headers,
                    oauth_token_manager=oauth_token_manager,
                )
            elif config.is_anthropic_format:
                from src.core.anthropic_client import AnthropicClient

                self._clients[cache_key] = AnthropicClient(
                    api_key=api_key_for_init,
                    base_url=config.base_url,
                    timeout=config.timeout,
                    custom_headers=config.custom_headers,
                    oauth_token_manager=oauth_token_manager,
                )
            else:
                self._clients[cache_key] = OpenAIClient(
                    api_key=api_key_for_init,
                    base_url=config.base_url,
                    timeout=config.timeout,
                    api_version=config.api_version,
                    custom_headers=config.custom_headers,
                    oauth_token_manager=oauth_token_manager,
                )

        return self._clients[cache_key]

    def has_client(self, provider_name: str) -> bool:
        """Check if a client exists for the given provider.

        Args:
            provider_name: The name of the provider.

        Returns:
            True if a cached client exists, False otherwise.
        """
        return provider_name in self._clients

    def clear(self) -> None:
        """Clear all cached clients.

        This is primarily useful for testing.
        """
        self._clients.clear()
