"""Unit tests for ResolutionTrace instrumentation in AliasManager.resolve_alias().

These tests verify that resolve_alias() populates a ResolutionTrace when
the optional ``trace`` keyword argument is provided, and that trace=None
produces identical behavior to calling without the parameter at all.

Design note: The trace is reconstructed from ResolutionResult fields rather
than threaded into the resolver chain. This avoids coupling trace infrastructure
to resolver internals -- the chain remains a pure strategy pipeline.
"""

import pytest

from src.core.alias_manager import AliasManager
from src.core.model_resolution_trace import ResolutionTrace


@pytest.fixture
def alias_manager_with_aliases() -> AliasManager:
    """Create an AliasManager with well-known aliases for deterministic tests.

    Bypasses env-var loading by directly setting the aliases dict and
    recreating the resolver chain, so tests run without side effects.
    """
    manager = AliasManager()
    manager.aliases = {
        "poe": {
            "haiku": "poe:grok-4.1-fast",
            "sonnet": "poe:grok-4.1",
            "intermediate": "poe:haiku",  # chained: intermediate -> haiku -> grok-4.1-fast
        },
        "openai": {
            "haiku": "openai:gpt-5.1-mini",
        },
    }
    manager._default_provider = "poe"
    manager._resolver_chain = manager._create_default_resolver_chain()
    return manager


class TestTraceExactMatch:
    """Exact alias match records resolver steps in trace."""

    @pytest.mark.unit
    def test_trace_exact_match(self, alias_manager_with_aliases: AliasManager) -> None:
        """Resolving 'haiku' (exact match) should record a 'matched' phase with resolver steps."""
        trace = ResolutionTrace(original_model="haiku")

        result = alias_manager_with_aliases.resolve_alias("haiku", trace=trace)

        # Verify the actual resolution still works
        assert result == "poe:grok-4.1-fast"

        # Exactly one phase should have been appended
        assert len(trace.phases) == 1
        phase = trace.phases[0]

        assert phase.name == "AliasManager resolution"
        assert phase.input == "haiku"
        assert phase.result == "matched"
        assert phase.output == "poe:grok-4.1-fast"
        assert phase.details["cache_hit"] is False

        # Resolver steps should be present in details
        resolver_steps = phase.details["resolver_steps"]
        assert isinstance(resolver_steps, list)
        assert len(resolver_steps) > 0

        # At least one resolver should have could_resolve=True and was_resolved=True
        resolved_steps = [s for s in resolver_steps if s["was_resolved"]]
        assert len(resolved_steps) >= 1


class TestTraceNoMatch:
    """No match records resolver steps with no resolution."""

    @pytest.mark.unit
    def test_trace_no_match(self, alias_manager_with_aliases: AliasManager) -> None:
        """Resolving an unknown model should record a 'no match' phase."""
        trace = ResolutionTrace(original_model="nonexistent-model-xyz")

        result = alias_manager_with_aliases.resolve_alias("nonexistent-model-xyz", trace=trace)

        # No alias found
        assert result is None

        # Phase should still be recorded
        assert len(trace.phases) == 1
        phase = trace.phases[0]

        assert phase.name == "AliasManager resolution"
        assert phase.input == "nonexistent-model-xyz"
        assert phase.result == "no match"
        assert phase.output == "nonexistent-model-xyz"
        assert phase.details["cache_hit"] is False

        # Resolution path should be empty for no-match
        assert phase.details["resolution_path"] == []


class TestTraceLiteralBypass:
    """Literal prefix !model records step in trace."""

    @pytest.mark.unit
    def test_trace_literal_bypass(self, alias_manager_with_aliases: AliasManager) -> None:
        """Resolving '!haiku' (literal bypass) should record the bypass in trace.

        The literal prefix '!' tells the resolver to skip alias resolution and
        use the model name as-is. resolve_alias() returns None for literals
        (LiteralPrefixResolver returns was_resolved=False), but the trace should
        still record that the LiteralPrefixResolver handled the request and
        what it would have produced.
        """
        trace = ResolutionTrace(original_model="!haiku")

        result = alias_manager_with_aliases.resolve_alias("!haiku", trace=trace)

        # resolve_alias() returns None for literal bypass (was_resolved=False)
        assert result is None

        # Phase should still be recorded
        assert len(trace.phases) == 1
        phase = trace.phases[0]

        assert phase.name == "AliasManager resolution"
        assert phase.input == "!haiku"
        # Literal bypass uses a distinct result label so debug output can
        # distinguish it from a true "no match" (unresolved alias attempt)
        assert phase.result == "literal bypass"
        assert phase.details["cache_hit"] is False

        # The resolver steps should show LiteralPrefixResolver participated
        resolver_steps = phase.details["resolver_steps"]
        literal_step = next(
            (s for s in resolver_steps if s["name"] == "LiteralPrefixResolver"), None
        )
        assert literal_step is not None
        assert literal_step["could_resolve"] is True
        # LiteralPrefixResolver marks was_resolved=True in our reconstruction
        # because it DID handle the request (just not as an alias match)
        assert literal_step["was_resolved"] is True
        assert literal_step["output_model"] == "poe:haiku"


class TestTraceNoneNoSideEffects:
    """trace=None produces identical result to calling without trace."""

    @pytest.mark.unit
    def test_trace_none_no_side_effects(self, alias_manager_with_aliases: AliasManager) -> None:
        """Passing trace=None should return the same result as omitting the parameter.

        This ensures the trace parameter is purely additive -- existing behavior
        is preserved when no trace is requested.
        """
        # Resolve without trace
        result_without = alias_manager_with_aliases.resolve_alias("haiku")

        # Resolve with trace=None
        result_with_none = alias_manager_with_aliases.resolve_alias("haiku", trace=None)

        # Clear cache so we get a fresh resolution
        alias_manager_with_aliases._cache.clear()

        # Resolve again without trace (cache cleared)
        result_fresh = alias_manager_with_aliases.resolve_alias("haiku")

        # All results must be identical
        assert result_without == result_with_none == result_fresh == "poe:grok-4.1-fast"


class TestTraceChainedAlias:
    """Chained alias records chain-following steps."""

    @pytest.mark.unit
    def test_trace_chained_alias(self, alias_manager_with_aliases: AliasManager) -> None:
        """Resolving 'intermediate' (which chains to 'haiku' -> 'grok-4.1-fast') should
        record the resolution path in the trace."""
        trace = ResolutionTrace(original_model="intermediate")

        result = alias_manager_with_aliases.resolve_alias("intermediate", trace=trace)

        # The chain should resolve: intermediate -> haiku -> poe:grok-4.1-fast
        assert result == "poe:grok-4.1-fast"

        # Phase should be recorded
        assert len(trace.phases) == 1
        phase = trace.phases[0]

        assert phase.name == "AliasManager resolution"
        assert phase.input == "intermediate"
        assert phase.result == "matched"
        assert phase.output == "poe:grok-4.1-fast"

        # The resolution_path should show the chain was followed
        resolution_path = phase.details["resolution_path"]
        assert "intermediate" in resolution_path or "haiku" in resolution_path


class TestTraceCacheHit:
    """Cache hit records cache_hit=True in trace details."""

    @pytest.mark.unit
    def test_trace_cache_hit(self, alias_manager_with_aliases: AliasManager) -> None:
        """Second resolution of the same model should record cache_hit=True."""
        trace_miss = ResolutionTrace(original_model="haiku")
        trace_hit = ResolutionTrace(original_model="haiku")

        # First call - cache miss (resolves through chain)
        result1 = alias_manager_with_aliases.resolve_alias("haiku", trace=trace_miss)
        assert result1 == "poe:grok-4.1-fast"
        assert trace_miss.phases[0].details["cache_hit"] is False

        # Second call - cache hit
        result2 = alias_manager_with_aliases.resolve_alias("haiku", trace=trace_hit)
        assert result2 == "poe:grok-4.1-fast"
        assert trace_hit.phases[0].details["cache_hit"] is True

        # Cache hit phase should have simpler details (no resolver_steps)
        assert "resolver_steps" not in trace_hit.phases[0].details
