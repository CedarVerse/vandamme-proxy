"""Timeout and connection configuration module.

This module handles timeout and connection-related settings including:
- Request timeout for non-streaming requests
- Streaming read and connect timeouts
- Maximum retry attempts

Now uses schema-based loading for automatic type coercion and validation.
"""

from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class TimeoutConfig:
    """Configuration for timeout and connection settings.

    Attributes:
        request_timeout: Timeout in seconds for non-streaming requests
        streaming_read_timeout: Timeout in seconds for SSE reads (None = unlimited)
        streaming_connect_timeout: Timeout in seconds for initial SSE connection
        max_retries: Maximum number of retry attempts for failed requests
    """

    request_timeout: int
    streaming_read_timeout: float | None
    streaming_connect_timeout: float
    max_retries: int


class TimeoutSettings:
    """Manages timeout and connection configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion (str -> int/float)
    - Validation with clear error messages
    - Single source of truth for default values
    - Proper handling of None for optional float values
    """

    @staticmethod
    def load() -> TimeoutConfig:
        """Load timeout configuration using schema-based validation.

        Returns:
            TimeoutConfig with values from environment or defaults

        Raises:
            ConfigError: If any environment variable fails validation
        """
        return TimeoutConfig(
            request_timeout=load_env_var(ConfigSchema.REQUEST_TIMEOUT),
            streaming_read_timeout=load_env_var(ConfigSchema.STREAMING_READ_TIMEOUT_SECONDS),
            streaming_connect_timeout=load_env_var(ConfigSchema.STREAMING_CONNECT_TIMEOUT_SECONDS),
            max_retries=load_env_var(ConfigSchema.MAX_RETRIES),
        )
