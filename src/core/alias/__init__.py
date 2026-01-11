"""Alias resolution strategy pattern implementation.

This module provides a flexible, composable alias resolution system
following the Strategy Pattern, inspired by the middleware architecture.
"""

from src.core.alias.resolver import (
    AliasResolver,
    AliasResolverChain,
    ChainedAliasResolver,
    LiteralPrefixResolver,
    MatchRanker,
    ResolutionContext,
    ResolutionResult,
    SubstringMatcher,
)

__all__ = [
    "AliasResolver",
    "AliasResolverChain",
    "ChainedAliasResolver",
    "LiteralPrefixResolver",
    "MatchRanker",
    "ResolutionContext",
    "ResolutionResult",
    "SubstringMatcher",
]
