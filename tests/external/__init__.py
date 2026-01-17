"""External tests for Vandamme Proxy.

External tests make real HTTP calls to external APIs and require:
1. A running proxy server
2. Valid API keys for the provider being tested
3. ALLOW_EXTERNAL_TESTS=1 environment variable

These tests are NOT run by default to prevent:
- Accidental API charges
- Flaky tests due to network issues
- Slow test runs during development
"""

__all__ = []
