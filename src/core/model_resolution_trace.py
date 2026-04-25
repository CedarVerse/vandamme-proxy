"""Data structures for tracing model resolution pipeline.

These dataclasses capture the full journey of a model name through the
resolution pipeline, recording each phase's input, output, and reasoning.
They are used by the ``vdm debug model-resolution`` CLI command to provide
transparent, step-by-step diagnostics of how a model name is resolved to
a concrete provider and model.

Design notes
------------
- ``ResolverStep`` and ``ResolutionPhase`` are **frozen** value objects
  because they represent immutable facts about a single resolution event.
- ``ResolutionTrace`` is **mutable** because phases are appended
  incrementally during resolution and ``final_provider`` / ``final_model``
  are set only after the pipeline completes.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolverStep:
    """Single resolver step within the AliasManager resolution phase.

    Each concrete resolver (``LiteralPrefixResolver``, ``SubstringResolver``,
    etc.) records whether it *could* attempt resolution and whether it
    *actually* resolved the model name.

    Attributes:
        name: Resolver class name (e.g., "LiteralPrefixResolver")
        could_resolve: Whether can_resolve() returned True
        was_resolved: Whether the resolver produced a result
        input_model: Model name before this resolver
        output_model: Model name after this resolver
        details: Resolver-specific context (e.g., which alias matched)
    """

    name: str
    could_resolve: bool
    was_resolved: bool
    input_model: str
    output_model: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResolutionPhase:
    """Single phase in the model resolution pipeline.

    A *phase* is a coarse-grained stage such as "Profile prefix detection"
    or "Alias resolution". Each phase may contain multiple ``ResolverStep``s
    internally, but the phase itself records the aggregate result.

    Attributes:
        name: Human-readable phase name (e.g., "Profile prefix detection")
        input: Model name entering this phase
        result: "matched", "skipped", or descriptive label
        output: Model name leaving this phase
        details: Phase-specific context for debugging
    """

    name: str
    input: str
    result: str
    output: str
    details: dict = field(default_factory=dict)


@dataclass  # Mutable accumulator — phases are appended during resolution
class ResolutionTrace:
    """Complete trace of the model resolution pipeline.

    Passed through the resolution pipeline and populated incrementally.
    At the end of resolution, ``final_provider`` and ``final_model``
    hold the resolved values.

    Attributes:
        original_model: The model name as provided by the caller
        phases: Ordered list of resolution phases executed
        final_provider: Provider name after full resolution
        final_model: Model name after full resolution
    """

    original_model: str
    phases: list[ResolutionPhase] = field(default_factory=list)
    final_provider: str = ""
    final_model: str = ""
