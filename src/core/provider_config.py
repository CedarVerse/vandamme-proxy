from dataclasses import dataclass, field

# Sentinel value for API key passthrough
PASSTHROUGH_SENTINEL = "!PASSTHRU"


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
        if self.api_keys is not None:
            # Mixed passthrough + real keys is ambiguous; reject in __post_init__.
            return False
        return self.api_key == PASSTHROUGH_SENTINEL

    def get_api_keys(self) -> list[str]:
        """Return the configured provider API keys (static mode only).

        Returns:
            List of API keys to use for upstream authentication.

        Raises:
            ValueError: if this provider is configured for passthrough.
        """
        if self.uses_passthrough:
            raise ValueError(f"Provider '{self.name}' is configured for passthrough")
        if self.api_keys is not None:
            return self.api_keys
        return [self.api_key]

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

        if self.api_keys is not None:
            if len(self.api_keys) == 0:
                raise ValueError(f"api_keys must be non-empty for provider '{self.name}'")
            if any(not k for k in self.api_keys):
                raise ValueError(
                    f"api_keys must not contain empty values for provider '{self.name}'"
                )
            if any(k == PASSTHROUGH_SENTINEL for k in self.api_keys):
                raise ValueError(
                    f"Provider '{self.name}' has mixed configuration: "
                    f"'!PASSTHRU' cannot be combined with static keys"
                )
            # Normalize api_key for backward compatibility/logging.
            self.api_key = self.api_keys[0]

        # Skip API key format validation for passthrough providers
        if not self.uses_passthrough and self.api_format == "openai":
            # Existing validation for OpenAI keys (can be extended based on requirements)
            pass
