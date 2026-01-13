"""Security and authentication configuration module.

This module handles security-related configuration including:
- Proxy API key for client authentication
- Client API key validation
- Custom HTTP headers from environment variables

Now uses schema-based loading for automatic type coercion and validation.
"""

import os
from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class SecurityConfig:
    """Configuration for security settings.

    Attributes:
        proxy_api_key: Optional API key for proxy authentication.
                      If set, clients must provide this key to access the proxy.
    """

    proxy_api_key: str | None


class SecuritySettings:
    """Manages security configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion
    - Validation with clear error messages
    - Single source of truth for default values
    """

    @staticmethod
    def load() -> SecurityConfig:
        """Load security configuration using schema-based validation.

        Returns:
            SecurityConfig with proxy API key if configured

        Raises:
            ConfigError: If any environment variable fails validation
        """
        return SecurityConfig(
            proxy_api_key=load_env_var(ConfigSchema.PROXY_API_KEY),
        )

    @staticmethod
    def validate_client_api_key(proxy_key: str | None, client_api_key: str) -> bool:
        """Validate a client's API key against the proxy requirement.

        If no proxy API key is configured, all clients are allowed.
        If a proxy API key is set, the client must provide an exact match.

        Args:
            proxy_key: The configured proxy API key (or None if not set)
            client_api_key: The API key provided by the client

        Returns:
            True if the client should be allowed, False otherwise
        """
        # If no PROXY_API_KEY is set, skip validation (open access)
        if not proxy_key:
            return True

        # Check if the client's API key matches the expected value
        return client_api_key == proxy_key

    @staticmethod
    def get_custom_headers() -> dict[str, str]:
        """Get custom HTTP headers from environment variables.

        Environment variables prefixed with CUSTOM_HEADER_ are converted
        to HTTP headers. For example, CUSTOM_HEADER_X_API_KEY becomes
        the X-API-KEY header.

        Underscores in the environment variable name are converted to
        hyphens in the header name.

        Returns:
            Dictionary of header name to header value
        """
        custom_headers = {}

        # Get all environment variables
        env_vars = dict(os.environ)

        # Find CUSTOM_HEADER_* environment variables
        for env_key, env_value in env_vars.items():
            if env_key.startswith("CUSTOM_HEADER_"):
                # Convert CUSTOM_HEADER_KEY to Header-Key
                # Remove 'CUSTOM_HEADER_' prefix
                header_name = env_key[len("CUSTOM_HEADER_") :]

                if header_name:  # Make sure it's not empty
                    # Convert underscores to hyphens for HTTP header format
                    header_name = header_name.replace("_", "-")
                    custom_headers[header_name] = env_value

        return custom_headers
