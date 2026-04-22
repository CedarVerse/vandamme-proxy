"""Unit tests for the 'responses' api_format support in ProviderConfig and ProviderConfigLoader.

The ChatGPT Responses API is a third wire-format alongside 'openai' and 'anthropic'.
These tests guard two critical invariants:

1. ProviderConfig.__post_init__ accepts "responses" without raising ValueError.
2. ProviderConfigLoader preserves "responses" all the way through to ProviderConfig
   rather than silently coercing it back to "openai" (the pre-fix bug).
"""

import pytest

from src.core.provider.provider_config_loader import ProviderConfigLoader
from src.core.provider_config import ProviderConfig

# ─── ProviderConfig unit tests ────────────────────────────────────────────────


@pytest.mark.unit
class TestProviderConfigResponsesFormat:
    """ProviderConfig correctly models the 'responses' api_format."""

    def _make_config(self, api_format: str) -> ProviderConfig:
        """Helper: build a minimal valid ProviderConfig with the given api_format."""
        return ProviderConfig(
            name="chatgpt",
            api_key="sk-test-key",
            base_url="https://chatgpt.com/backend-api",
            api_format=api_format,
        )

    def test_responses_format_is_accepted(self):
        """ProviderConfig(api_format='responses') must not raise ValueError.

        Before this fix, __post_init__ rejected any value other than 'openai'
        or 'anthropic', making it impossible to configure the Responses API.
        """
        # Should not raise
        config = self._make_config("responses")
        assert config.api_format == "responses"

    def test_is_responses_format_true_for_responses(self):
        """is_responses_format returns True only when api_format == 'responses'."""
        config = self._make_config("responses")
        assert config.is_responses_format is True

    def test_is_responses_format_false_for_openai(self):
        """is_responses_format is False for the 'openai' format."""
        config = self._make_config("openai")
        assert config.is_responses_format is False

    def test_is_responses_format_false_for_anthropic(self):
        """is_responses_format is False for the 'anthropic' format."""
        config = self._make_config("anthropic")
        assert config.is_responses_format is False

    def test_is_anthropic_format_unaffected_by_responses(self):
        """Adding 'responses' must not break the existing is_anthropic_format property."""
        assert self._make_config("anthropic").is_anthropic_format is True
        assert self._make_config("openai").is_anthropic_format is False
        assert self._make_config("responses").is_anthropic_format is False

    def test_unknown_format_still_raises(self):
        """An unrecognised api_format still raises ValueError (no regression)."""
        with pytest.raises(ValueError, match="Invalid API format"):
            self._make_config("graphql")

    def test_error_message_lists_all_valid_formats(self):
        """The ValueError for unknown formats mentions all three valid options."""
        with pytest.raises(ValueError, match="'openai', 'anthropic', or 'responses'"):
            self._make_config("grpc")


# ─── ProviderConfigLoader integration tests ───────────────────────────────────


@pytest.mark.unit
class TestProviderConfigLoaderResponsesFormat:
    """ProviderConfigLoader preserves api_format='responses' from env/TOML to ProviderConfig.

    Three separate code paths in the loader each had the silent coercion bug;
    we test the one exercised by load_provider() which is the most common entry point.
    """

    def test_load_provider_preserves_responses_format_from_env(self, monkeypatch):
        """load_provider() must NOT coerce RESPTEST_API_FORMAT=responses → 'openai'.

        This was the CRITICAL blocker: the loader had
            if api_format not in ("openai", "anthropic"):
                api_format = "openai"
        which silently discarded the 'responses' value.

        We use a synthetic provider name ("resptest") with no matching TOML defaults
        so the test is isolated from config-file side-effects.
        """
        monkeypatch.setenv("RESPTEST_API_KEY", "sk-test-key")
        monkeypatch.setenv("RESPTEST_BASE_URL", "https://chatgpt.com/backend-api")
        monkeypatch.setenv("RESPTEST_API_FORMAT", "responses")

        loader = ProviderConfigLoader()
        config = loader.load_provider("resptest", require_api_key=True)

        assert config is not None
        assert config.api_format == "responses"
        assert config.is_responses_format is True

    def test_load_provider_defaults_to_openai_when_unset(self, monkeypatch):
        """Baseline: loader still defaults to 'openai' when no format is configured."""
        monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
        monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
        # Deliberately do NOT set TESTPROV_API_FORMAT

        loader = ProviderConfigLoader()
        config = loader.load_provider("testprov", require_api_key=True)

        assert config is not None
        assert config.api_format == "openai"

    def test_load_provider_falls_back_to_openai_for_unknown_format(self, monkeypatch, caplog):
        """Unknown formats emit a warning and fall back to 'openai' (not a hard error).

        The loader is intentionally lenient here: raising an exception would break
        proxy startup for a misconfigured secondary provider.  The warning makes the
        issue visible in logs without bringing down the service.
        """
        monkeypatch.setenv("TESTPROV_API_KEY", "test-key")
        monkeypatch.setenv("TESTPROV_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("TESTPROV_API_FORMAT", "grpc_streaming")

        loader = ProviderConfigLoader()
        import logging

        with caplog.at_level(logging.WARNING):
            config = loader.load_provider("testprov", require_api_key=True)

        assert config is not None
        assert config.api_format == "openai"
        assert any("grpc_streaming" in record.message for record in caplog.records)
        assert any("Unknown api_format" in record.message for record in caplog.records)

    def test_load_provider_preserves_anthropic_format(self, monkeypatch):
        """Baseline: existing 'anthropic' format still works after the refactor."""
        monkeypatch.setenv("MYPROV_API_KEY", "sk-ant-test")
        monkeypatch.setenv("MYPROV_BASE_URL", "https://api.anthropic.com")
        monkeypatch.setenv("MYPROV_API_FORMAT", "anthropic")

        loader = ProviderConfigLoader()
        config = loader.load_provider("myprov", require_api_key=True)

        assert config is not None
        assert config.api_format == "anthropic"
        assert config.is_anthropic_format is True
        assert config.is_responses_format is False

    def test_load_default_provider_preserves_responses_format(self, monkeypatch):
        """_load_default_provider() must NOT coerce DFLTTEST_API_FORMAT=responses → 'openai'.

        This path is reached when the loader initialises the *default* provider
        (i.e. the one pointed at by VDM_DEFAULT_TARGET).  It shared the same silent
        coercion bug as load_provider() and also had a missing ``api_keys is not None``
        guard that would have raised TypeError on OAuth mode.  Both are fixed; this
        test guards the format-preservation invariant.

        We call the private method directly to avoid the overhead of spinning up a full
        ProviderManager, using a lightweight MagicMock for the registry (the method
        only calls registry.register(config)).
        """
        from unittest.mock import MagicMock

        monkeypatch.setenv("DFLTTEST_API_KEY", "sk-default-test")
        monkeypatch.setenv("DFLTTEST_BASE_URL", "https://dflt.example.com/v1")
        monkeypatch.setenv("DFLTTEST_API_FORMAT", "responses")

        loader = ProviderConfigLoader()
        mock_registry = MagicMock()
        # default_selector is accepted by the method but not used in its body
        mock_selector = MagicMock()

        result = loader._load_default_provider("dflttest", mock_selector, mock_registry)

        assert result is not None
        assert result.status == "success"
        # The config passed to registry.register() must carry api_format='responses'
        registered_config = mock_registry.register.call_args[0][0]
        assert registered_config.api_format == "responses"
        assert registered_config.is_responses_format is True

    def test_load_provider_config_with_result_preserves_responses_format(self, monkeypatch):
        """_load_provider_config_with_result() must NOT coerce ADDLTEST_API_FORMAT=responses.

        This path is reached when the loader processes *additional* (non-default)
        providers — discovered either from TOML sections or from ``*_API_KEY`` env-var
        scanning.  It is a separate code path from both load_provider() and
        _load_default_provider(), so it needs its own regression guard.
        """
        from unittest.mock import MagicMock

        monkeypatch.setenv("ADDLTEST_API_KEY", "sk-addl-test")
        monkeypatch.setenv("ADDLTEST_BASE_URL", "https://addl.example.com/v1")
        monkeypatch.setenv("ADDLTEST_API_FORMAT", "responses")

        loader = ProviderConfigLoader()
        mock_registry = MagicMock()

        result = loader._load_provider_config_with_result("addltest", mock_registry)

        assert result is not None
        assert result.status == "success"
        # The config passed to registry.register() must carry api_format='responses'
        registered_config = mock_registry.register.call_args[0][0]
        assert registered_config.api_format == "responses"
        assert registered_config.is_responses_format is True
