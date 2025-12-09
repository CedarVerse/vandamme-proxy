from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ProviderConfig:
    """Configuration for a specific provider"""

    name: str
    api_key: str
    base_url: str
    api_version: Optional[str] = None
    timeout: int = 90
    max_retries: int = 2
    custom_headers: Dict[str, str] = field(default_factory=dict)

    @property
    def is_azure(self) -> bool:
        """Check if this is an Azure OpenAI provider"""
        return self.api_version is not None

    def __post_init__(self) -> None:
        """Validate configuration after initialization"""
        if not self.name:
            raise ValueError("Provider name is required")
        if not self.api_key:
            raise ValueError(f"API key is required for provider '{self.name}'")
        if not self.base_url:
            raise ValueError(f"Base URL is required for provider '{self.name}'")
