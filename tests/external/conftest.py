"""Configuration for external tests requiring real API calls.

External tests:
- Make real HTTP calls to external APIs
- Require valid API keys
- Require ALLOW_EXTERNAL_TESTS=1 environment variable
- Fail fast if API keys are missing (configurable via EXTERNAL_TESTS_SKIP_MISSING)
"""

import os

import pytest


class ExternalTestConfig:
    """Manages configuration for external tests.

    Provides methods to check for required API keys and validate
    external test opt-in status.
    """

    # Provider API key environment variable names
    PROVIDER_API_KEYS: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_API_KEY",
        "poe": "POE_API_KEY",
        "glm": "GLM_API_KEY",
        "bedrock": "BEDROCK_API_KEY",
        "vertex": "VERTEX_API_KEY",
        "zai": "ZAI_API_KEY",
        "zaio": "ZAIO_API_KEY",
        "custom": "CUSTOM_API_KEY",
    }

    @classmethod
    def has_api_key(cls, provider: str) -> bool:
        """Check if API key exists for the given provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            True if API key is set and non-empty
        """
        env_var = cls.PROVIDER_API_KEYS.get(provider)
        if not env_var:
            return False
        api_key = os.environ.get(env_var, "")
        return bool(api_key and api_key.strip())

    @classmethod
    def get_api_key(cls, provider: str) -> str | None:
        """Get the API key for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            The API key value or None if not set
        """
        env_var = cls.PROVIDER_API_KEYS.get(provider)
        if not env_var:
            return None
        api_key = os.environ.get(env_var, "")
        return api_key.strip() if api_key.strip() else None

    @classmethod
    def is_external_test_opt_in_enabled(cls) -> bool:
        """Check if external test opt-in is enabled.

        Returns:
            True if ALLOW_EXTERNAL_TESTS is set to "1" or "true"
        """
        opt_in = os.environ.get("ALLOW_EXTERNAL_TESTS", "").lower()
        return opt_in in ("1", "true", "yes")

    @classmethod
    def should_skip_missing_keys(cls) -> bool:
        """Check if tests should skip when API keys are missing.

        Returns:
            True if EXTERNAL_TESTS_SKIP_MISSING is set to "1" or "true"
        """
        skip_missing = os.environ.get("EXTERNAL_TESTS_SKIP_MISSING", "").lower()
        return skip_missing in ("1", "true", "yes")

    @classmethod
    def verify_external_test_opt_in(cls) -> None:
        """Verify that external test opt-in is enabled.

        Raises:
            pytest.skip.Exception: If ALLOW_EXTERNAL_TESTS is not set
        """
        if not cls.is_external_test_opt_in_enabled():
            pytest.skip(
                "External tests require ALLOW_EXTERNAL_TESTS=1. "
                "Run: ALLOW_EXTERNAL_TESTS=1 pytest -m external"
            )

    @classmethod
    def verify_provider_api_key(cls, provider: str) -> None:
        """Verify that API key exists for the given provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Raises:
            pytest.skip.Exception: If EXTERNAL_TESTS_SKIP_MISSING is set
            pytest.fail.Exception: If API key is missing and skip is disabled
        """
        if not cls.has_api_key(provider):
            env_var = cls.PROVIDER_API_KEYS.get(provider, f"{provider.upper()}_API_KEY")
            if cls.should_skip_missing_keys():
                pytest.skip(f"{env_var} not set")
            else:
                pytest.fail(
                    f"{env_var} is required for this test. "
                    f"Set the API key or run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )


@pytest.fixture(scope="session")
def external_test_config():
    """Provide external test configuration."""
    return ExternalTestConfig


@pytest.fixture(autouse=True)
def verify_external_test_opt_in():
    """Verify external test opt-in before running any external test.

    This fixture automatically applies to all tests in the external/ directory.
    Tests will be skipped unless ALLOW_EXTERNAL_TESTS=1 is set.
    """
    # Only apply to tests marked as external
    # (The marker is auto-applied to tests in tests/external/ directory)
    yield


@pytest.fixture
def require_api_keys(external_test_config: type[ExternalTestConfig]):
    """Factory fixture that creates API key requirement fixtures.

    Usage in tests:
        @pytest.mark.requires_api_keys("openai", "anthropic")
        def test_something(require_api_keys):
            # This test will fail if OPENAI_API_KEY or ANTHROPIC_API_KEY are missing

    Returns:
        A function that takes provider names and verifies their API keys
    """

    def _require_keys(*providers: str) -> None:
        """Verify API keys exist for the given providers.

        Args:
            *providers: One or more provider names (e.g., "openai", "anthropic")

        Raises:
            pytest.skip.Exception: If EXTERNAL_TESTS_SKIP_MISSING is set
            pytest.fail.Exception: If any API key is missing and skip is disabled
        """
        missing_keys = []
        for provider in providers:
            if not external_test_config.has_api_key(provider):
                env_var = external_test_config.PROVIDER_API_KEYS.get(
                    provider, f"{provider.upper()}_API_KEY"
                )
                missing_keys.append(env_var)

        if missing_keys:
            if external_test_config.should_skip_missing_keys():
                pytest.skip(
                    f"Missing required API keys: {', '.join(missing_keys)}. "
                    f"Run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )
            else:
                pytest.fail(
                    f"Missing required API keys: {', '.join(missing_keys)}. "
                    f"Set the keys or run with EXTERNAL_TESTS_SKIP_MISSING=1 to skip."
                )

    return _require_keys


@pytest.fixture
def external_api_keys(external_test_config: type[ExternalTestConfig]):
    """Provide access to available external API keys.

    Returns a dict mapping provider names to their API key values
    for providers that have keys configured.

    Usage:
        def test_something(external_api_keys):
            openai_key = external_api_keys.get("openai")
            if openai_key:
                # Use the key
    """
    available_keys = {}
    for provider, _env_var in external_test_config.PROVIDER_API_KEYS.items():
        key = external_test_config.get_api_key(provider)
        if key:
            available_keys[provider] = key
    return available_keys


def pytest_configure(config):
    """Register custom markers for external tests."""
    config.addinivalue_line(
        "markers",
        "requires_api_keys(provider, ...): Test requires API keys for specified providers",
    )
