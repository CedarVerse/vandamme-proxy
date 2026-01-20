"""Server configuration module.

This module handles server-related configuration including:
- Server host
- Server port
- Logging level

Now uses schema-based loading for automatic type coercion and validation.
"""

from dataclasses import dataclass

from src.core.config.schema import ConfigSchema
from src.core.config.validation import load_env_var


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for server settings.

    Attributes:
        host: Server host address to bind to
        port: Server port number
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        strict_profile_validation: Fail startup on profile validation errors
    """

    host: str
    port: int
    log_level: str
    strict_profile_validation: bool


class ServerSettings:
    """Manages server configuration from environment variables.

    This class uses the schema-based loading approach which provides:
    - Automatic type coercion (str -> int)
    - Validation with clear error messages
    - Single source of truth for default values
    """

    @staticmethod
    def load() -> ServerConfig:
        """Load server configuration using schema-based validation.

        Returns:
            ServerConfig with values from environment or defaults

        Raises:
            ConfigError: If any environment variable fails validation
        """
        return ServerConfig(
            host=load_env_var(ConfigSchema.HOST),
            port=load_env_var(ConfigSchema.PORT),
            log_level=load_env_var(ConfigSchema.LOG_LEVEL),
            strict_profile_validation=load_env_var(ConfigSchema.VDM_STRICT_PROFILE_VALIDATION),
        )
