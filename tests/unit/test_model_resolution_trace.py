"""Unit tests for ResolutionTrace instrumentation in ModelManager.resolve_model().

These tests verify that resolve_model() populates a ResolutionTrace when
the optional ``trace`` keyword argument is provided, and that trace=None
produces identical behavior to calling without the parameter at all.

The ModelManager orchestrates the full resolution pipeline:
  1. Profile prefix detection ("top:haiku" -> strip profile prefix)
  2. Default profile resolution (bare name + default_profile -> set profile)
  3. Profile alias lookup (exact match in profile.aliases)
  4. AliasManager resolution (substring match, chained, ranked)
  5. Provider prefix parsing ("openai:gpt-5.1" -> ("openai", "gpt-5.1"))

Each phase is recorded with input, result ("matched"/"skipped"), output,
and details dict for debugging context.
"""

from unittest.mock import Mock

import pytest

from src.core.model_manager import ModelManager
from src.core.model_resolution_trace import ResolutionPhase, ResolutionTrace


@pytest.fixture
def mock_config() -> Mock:
    """Create a mock ConfigProvider with all dependencies stubbed out.

    By default:
    - profile_manager reports no profiles exist (is_profile -> False)
    - default_target is "poe"
    - no default_profile set
    - alias_manager reports no aliases configured
    """
    config = Mock()
    profile_manager = Mock()
    profile_manager.is_profile.return_value = False
    profile_manager.get_profile.return_value = None
    config.provider_manager.profile_manager = profile_manager
    config.provider_manager.default_target = "poe"
    config.provider_manager.default_profile = None
    config.provider_manager.parse_model_name = lambda m: (
        m.split(":", 1) if ":" in m else ("poe", m)
    )
    alias_manager = Mock()
    alias_manager.has_aliases.return_value = False
    alias_manager.resolve_alias.return_value = None
    config.alias_manager = alias_manager
    return config


# ---------------------------------------------------------------------------
# Test 1: Bare model with no aliases passes through to default provider
# ---------------------------------------------------------------------------


class TestBareModelNoAliases:
    """Bare model name without aliases should record all phases and resolve to default provider."""

    @pytest.mark.unit
    def test_bare_model_no_aliases(self, mock_config: Mock) -> None:
        """Resolving 'gpt-5.1' with no aliases should record 5 phases and resolve to poe:gpt-5.1."""
        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="gpt-5.1")

        provider, model = manager.resolve_model("gpt-5.1", trace=trace)

        assert provider == "poe"
        assert model == "gpt-5.1"
        assert trace.final_provider == "poe"
        assert trace.final_model == "gpt-5.1"

        # Verify we have all 5 phases recorded
        phase_names = [p.name for p in trace.phases]
        assert "Profile prefix detection" in phase_names
        assert "Default profile resolution" in phase_names
        assert "Profile alias lookup" in phase_names
        assert "AliasManager" in phase_names or "AliasManager resolution" in phase_names
        assert "Provider prefix parsing" in phase_names

        # Profile prefix detection should be skipped (no colon)
        ppd = _find_phase(trace, "Profile prefix detection")
        assert ppd.result == "skipped"
        assert "no colon" in ppd.details.get("reason", "")

        # Default profile resolution should be skipped (no default profile)
        dpr = _find_phase(trace, "Default profile resolution")
        assert dpr.result == "skipped"
        assert "no default profile" in dpr.details.get("reason", "")


# ---------------------------------------------------------------------------
# Test 2: Profile prefix resolution
# ---------------------------------------------------------------------------


class TestProfilePrefixResolution:
    """'top:haiku' should detect profile prefix and strip it."""

    @pytest.mark.unit
    def test_profile_prefix_resolution(self, mock_config: Mock) -> None:
        """Resolving 'top:haiku' should detect 'top' as profile and resolve 'haiku'."""
        mock_profile = Mock()
        mock_profile.name = "top"
        mock_profile.aliases = {"haiku": "openai:gpt-5.1-mini"}

        mock_config.provider_manager.profile_manager.is_profile.return_value = True
        mock_config.provider_manager.profile_manager.get_profile.return_value = mock_profile

        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="top:haiku")

        provider, model = manager.resolve_model("top:haiku", trace=trace)

        assert provider == "openai"
        assert model == "gpt-5.1-mini"

        # Profile prefix detection should have matched
        ppd = _find_phase(trace, "Profile prefix detection")
        assert ppd.result == "matched"
        assert ppd.output == "haiku"
        assert ppd.details.get("potential_profile") == "top"
        assert ppd.details.get("profile_name") == "top"

        # Profile alias lookup should have matched
        pal = _find_phase(trace, "Profile alias lookup")
        assert pal.result == "matched"
        assert pal.output == "openai:gpt-5.1-mini"
        assert pal.details.get("alias_key") == "haiku"
        assert pal.details.get("alias_target") == "openai:gpt-5.1-mini"


# ---------------------------------------------------------------------------
# Test 3: Default profile applied for bare model
# ---------------------------------------------------------------------------


class TestDefaultProfileApplied:
    """When default_profile is set, bare models should get the profile applied."""

    @pytest.mark.unit
    def test_default_profile_applied(self, mock_config: Mock) -> None:
        """Resolving 'haiku' with default_profile='top' should apply top profile aliases."""
        mock_profile = Mock()
        mock_profile.name = "top"
        mock_profile.aliases = {"haiku": "openai:gpt-5.1-mini"}

        mock_config.provider_manager.default_profile = "top"
        mock_config.provider_manager.profile_manager.is_profile.return_value = True
        mock_config.provider_manager.profile_manager.get_profile.return_value = mock_profile

        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="haiku")

        provider, model = manager.resolve_model("haiku", trace=trace)

        assert provider == "openai"
        assert model == "gpt-5.1-mini"

        # Default profile resolution should have matched
        dpr = _find_phase(trace, "Default profile resolution")
        assert dpr.result == "matched"
        assert dpr.details.get("default_target") == "top"
        assert dpr.details.get("profile_name") == "top"

        # Profile alias lookup should have matched
        pal = _find_phase(trace, "Profile alias lookup")
        assert pal.result == "matched"


# ---------------------------------------------------------------------------
# Test 4: trace=None produces identical result to no trace
# ---------------------------------------------------------------------------


class TestNonRegressionTraceNone:
    """trace=None should produce exactly the same result as omitting trace."""

    @pytest.mark.unit
    def test_non_regression_trace_none(self, mock_config: Mock) -> None:
        """Calling with trace=None should return same (provider, model) as without trace."""
        manager = ModelManager(mock_config)

        # Configure a profile to exercise more of the code path
        mock_profile = Mock()
        mock_profile.name = "top"
        mock_profile.aliases = {"haiku": "openai:gpt-5.1-mini"}
        mock_config.provider_manager.profile_manager.is_profile.return_value = True
        mock_config.provider_manager.profile_manager.get_profile.return_value = mock_profile

        result_no_trace = manager.resolve_model("top:haiku")
        result_with_none = manager.resolve_model("top:haiku", trace=None)

        assert result_no_trace == result_with_none
        assert result_with_none == ("openai", "gpt-5.1-mini")


# ---------------------------------------------------------------------------
# Test 5: Phases are found by name, not by index
# ---------------------------------------------------------------------------


class TestTraceByPhaseNameNotIndex:
    """Trace phases should be looked up by name, not by fragile index."""

    @pytest.mark.unit
    def test_trace_by_phase_name_not_index(self, mock_config: Mock) -> None:
        """All phases should be accessible by name via a helper, not by list index."""
        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="gpt-5.1")

        manager.resolve_model("gpt-5.1", trace=trace)

        # Verify we can find each expected phase by name
        expected_phases = [
            "Profile prefix detection",
            "Default profile resolution",
            "Profile alias lookup",
            "AliasManager",
            "Provider prefix parsing",
        ]
        for name in expected_phases:
            phase = _find_phase(trace, name)
            assert phase is not None, f"Expected phase '{name}' not found in trace"
            assert phase.name == name


# ---------------------------------------------------------------------------
# Test 6: Provider prefix parsing
# ---------------------------------------------------------------------------


class TestProviderPrefixModel:
    """'openai:gpt-5.1' should parse through provider prefix, not profile prefix."""

    @pytest.mark.unit
    def test_provider_prefix_model(self, mock_config: Mock) -> None:
        """Resolving 'openai:gpt-5.1' should parse provider prefix, not profile prefix."""
        # 'openai' is NOT a profile
        mock_config.provider_manager.profile_manager.is_profile.return_value = False

        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="openai:gpt-5.1")

        provider, model = manager.resolve_model("openai:gpt-5.1", trace=trace)

        assert provider == "openai"
        assert model == "gpt-5.1"

        # Profile prefix detection should be skipped (openai is not a profile)
        ppd = _find_phase(trace, "Profile prefix detection")
        assert ppd.result == "skipped"

        # Provider prefix parsing should show the final parse
        ppp = _find_phase(trace, "Provider prefix parsing")
        assert ppp.result == "parsed"
        assert ppp.details.get("provider") == "openai"
        assert ppp.details.get("model") == "gpt-5.1"


# ---------------------------------------------------------------------------
# Test 7: Literal bypass model (!gpt-5.1) skips profile resolution
# ---------------------------------------------------------------------------


class TestLiteralBypassModel:
    """'!gpt-5.1' should skip profile resolution due to literal bypass prefix."""

    @pytest.mark.unit
    def test_literal_bypass_model(self, mock_config: Mock) -> None:
        """Resolving '!gpt-5.1' should skip profile resolution and pass through."""
        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="!gpt-5.1")

        provider, model = manager.resolve_model("!gpt-5.1", trace=trace)

        assert provider == "poe"
        assert model == "!gpt-5.1"

        # Profile prefix detection should be skipped (no colon)
        ppd = _find_phase(trace, "Profile prefix detection")
        assert ppd.result == "skipped"

        # Default profile resolution should be skipped (literal bypass)
        dpr = _find_phase(trace, "Default profile resolution")
        assert dpr.result == "skipped"
        assert "literal bypass" in dpr.details.get("reason", "").lower()

        # Profile alias lookup should be skipped (no active profile)
        pal = _find_phase(trace, "Profile alias lookup")
        assert pal.result == "skipped"


# ---------------------------------------------------------------------------
# Test 8: Every skipped phase includes a reason
# ---------------------------------------------------------------------------


class TestSkippedPhaseHasReason:
    """All skipped phases must include a 'reason' key in their details dict.

    This is a contract: when a phase is skipped, callers (especially
    the 'vdm debug model-resolution' CLI) need to know *why* to produce
    clear diagnostic output.
    """

    @pytest.mark.unit
    def test_skipped_phase_has_reason(self, mock_config: Mock) -> None:
        """Every skipped phase in the trace should have a 'reason' in details."""
        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="gpt-5.1")

        manager.resolve_model("gpt-5.1", trace=trace)

        skipped_phases = [p for p in trace.phases if p.result == "skipped"]
        assert len(skipped_phases) > 0, (
            "Expected at least one skipped phase for bare model with no aliases"
        )

        for phase in skipped_phases:
            assert "reason" in phase.details, (
                f"Skipped phase '{phase.name}' is missing 'reason' in details. "
                f"Details: {phase.details}"
            )
            assert phase.details["reason"], f"Skipped phase '{phase.name}' has empty reason string"


# ---------------------------------------------------------------------------
# Test 9: Trace records final result
# ---------------------------------------------------------------------------


class TestTraceRecordsFinalResult:
    """After resolution, trace.final_provider and trace.final_model should be set."""

    @pytest.mark.unit
    def test_trace_records_final_result(self, mock_config: Mock) -> None:
        """Trace should capture the final (provider, model) after full resolution."""
        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="gpt-5.1")

        provider, model = manager.resolve_model("gpt-5.1", trace=trace)

        assert trace.final_provider == provider
        assert trace.final_model == model
        assert trace.original_model == "gpt-5.1"

    @pytest.mark.unit
    def test_trace_records_final_result_with_alias(self, mock_config: Mock) -> None:
        """Trace should capture the resolved (provider, model) when alias is applied."""
        # Set up a profile with an alias that changes the provider
        mock_profile = Mock()
        mock_profile.name = "top"
        mock_profile.aliases = {"haiku": "anthropic:claude-3-5-haiku"}
        mock_config.provider_manager.profile_manager.is_profile.return_value = True
        mock_config.provider_manager.profile_manager.get_profile.return_value = mock_profile

        manager = ModelManager(mock_config)
        trace = ResolutionTrace(original_model="top:haiku")

        provider, model = manager.resolve_model("top:haiku", trace=trace)

        assert trace.final_provider == provider == "anthropic"
        assert trace.final_model == model == "claude-3-5-haiku"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_phase(trace: ResolutionTrace, name: str) -> ResolutionPhase | None:
    """Find a phase by name (case-sensitive). Returns None if not found.

    This helper exists to make tests robust against phase ordering changes
    -- we assert by semantic name, not by fragile list index.
    """
    for phase in trace.phases:
        if phase.name == name:
            return phase
    return None
