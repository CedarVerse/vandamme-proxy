"""Core exceptions for Vandamme Proxy.

This module defines the base exception hierarchy used throughout
the application for configuration, validation, and runtime errors.
"""


class VandammeError(Exception):
    """Base exception for all Vandamme Proxy errors.

    All library-specific exceptions inherit from this, allowing
    users to catch all library errors with a single except clause.

    Example:
        >>> try:
        ...     manager.get_client("unknown")
        ... except VandammeError as e:
        ...     print(f"Operation failed: {e}")
    """

    pass


class ConfigurationError(VandammeError):
    """Raised when configuration is invalid or incomplete.

    This exception indicates a configuration problem such as:
    - Missing required configuration values
    - Invalid configuration values (null, negative, wrong type)
    - Configuration that violates validation rules

    Example:
        >>> # Missing required timeout configuration
        >>> ConfigurationError: Required configuration 'timeout' not found
        >>> for provider 'poe'. Please define it in one of:
        >>>   1. Environment variable: REQUEST_TIMEOUT
        >>>   2. Provider config: [poe] timeout = <value>
        >>>   3. Global defaults: [defaults] timeout = <value>
    """

    pass


__all__ = ["VandammeError", "ConfigurationError"]
