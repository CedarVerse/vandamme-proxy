from dataclasses import dataclass, field

# Sentinel value for API key passthrough
PASSTHROUGH_SENTINEL = "!PASSTHRU"


@dataclass
class ProviderConfig:
    """Configuration for a specific provider"""

    name: str
    api_key: str
    base_url: str
    api_version: str | None = None
    timeout: int = 90
    max_retries: int = 2
    custom_headers: dict[str, str] = field(default_factory=dict)
    api_format: str = "openai"  # "openai" or "anthropic"

    @property
    def is_azure(self) -> bool:
        """Check if this is an Azure OpenAI provider"""
        return self.api_version is not None

    @property
    def is_anthropic_format(self) -> bool:
        """Check if this provider uses Anthropic API format"""
        return self.api_format == "anthropic"

    @property
    def uses_passthrough(self) -> bool:
        """Check if this provider uses client API key passthrough"""
        return self.api_key == PASSTHROUGH_SENTINEL

    def get_effective_api_key(self, client_api_key: str | None = None) -> str | None:
        """Get the API key to use for requests

        Args:
            client_api_key: The client's API key from request headers

        Returns:
            The API key to use for external requests
        """
        if self.uses_passthrough:
            return client_api_key
        return self.api_key

    def __post_init__(self) -> None:
        """Validate configuration after initialization"""
        if not self.name:
            raise ValueError("Provider name is required")
        if not self.api_key:
            raise ValueError(f"API key is required for provider '{self.name}'")
        if not self.base_url:
            raise ValueError(f"Base URL is required for provider '{self.name}'")
        if self.api_format not in ["openai", "anthropic"]:
            raise ValueError(
                f"Invalid API format '{self.api_format}' for provider '{self.name}'. "
                "Must be 'openai' or 'anthropic'"
            )

        # Skip API key format validation for passthrough providers
        if not self.uses_passthrough and self.api_format == "openai":
            # Existing validation for OpenAI keys (can be extended based on requirements)
            # For now, we just ensure it's not the sentinel value
            pass
