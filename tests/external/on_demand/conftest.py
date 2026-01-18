"""Configuration for on-demand external tests.

On-demand tests are expensive external tests that should be run selectively
via `make test-on-demand PATTERN=<pattern>` rather than as part of the
regular test suite.

Markers:
- Tests in this directory automatically receive both `on_demand` and `external` markers
- Marker auto-application is handled by tests/conftest.py:pytest_collection_modifyitems
- Marker registration is handled by tests/conftest.py:pytest_configure

Environment:
- ALLOW_EXTERNAL_TESTS=1 must be set (done via Makefile target)
- Required API keys must be set (e.g., POE_API_KEY)
"""

# This file is intentionally minimal - all configuration is centralized in tests/conftest.py
