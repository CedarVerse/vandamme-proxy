"""Configuration module for Vandamme Proxy.

This package provides a modular configuration system with focused modules
for different configuration domains.

The configuration is split into focused modules:
- schema: Declarative environment variable specifications
- validation: Type coercion and validation utilities
- provider_utils: Provider-related utility functions
- providers: Provider configuration (default provider, API keys, base URLs)
- server: Server settings (host, port, logging)
- security: Authentication and validation (proxy API key, custom headers)
- timeouts: Connection settings (timeouts, retries, streaming)
- cache: Cache configuration (models cache, alias cache)
- metrics: Metrics and monitoring (token limits, SSE settings)
- middleware: Middleware configuration (thought signatures)
- top_models: Top models feature configuration
- lazy_managers: Lazy initialization for provider/alias managers
- config: Main Config singleton

Public API:
    Config: The main configuration class
    config: The global configuration singleton

Example:
    from src.core.config import config

    provider = config.default_provider
    port = config.port
"""

from src.core.config.config import Config, config

__all__ = ["Config", "config"]
