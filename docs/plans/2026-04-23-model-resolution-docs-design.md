# Design: Model Resolution Documentation Overhaul

**Date:** 2026-04-23
**Status:** Approved

## Problem

Model aliasing and profile resolution are poorly documented across the codebase. The audit found 6 major gaps:

1. **Profile aliases** — barely documented anywhere; the new default-profile inheritance feature has zero user-facing docs
2. **`!` literal prefix** — implemented but invisible in all documentation
3. **Resolver chain architecture** — only documented in code comments
4. **MatchRanker tie-breaking** — documented incorrectly (missing default-target preference)
5. **Fallback alias tables** — inconsistent across documents (CLAUDE.md vs docs/)
6. **Chained alias resolution** — undocumented capability (aliases pointing to aliases)

Users are confused about what happens when they type a bare model name like `opus` and it resolves differently than expected.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Approach | Pipeline-first | Mirrors user mental model ("what happened to my model name?") |
| Audience | Layered | User guide first, developer reference as appendix |
| Location | `docs/model-resolution.md` | Single authoritative source |
| Scope | Full | New guide + fix inconsistencies + wire references + fix docstring |

## Deliverables

### 1. New file: `docs/model-resolution.md`

**Structure:**

```
Title: Model Name Resolution Guide

1. Overview (2-3 sentences)

2. Resolution Pipeline
   - ASCII flow diagram showing 7 phases
   - Summary table: Phase | Input | Output | Example

3. Phase 1: Profile Prefix Detection
   - "profile:model" syntax
   - Profile takes precedence over same-name provider
   - Example: "webdev-good:haiku"

4. Phase 2: Default Profile Inheritance
   - When VDM_DEFAULT_TARGET is a profile name
   - Bare names inherit the profile's aliases
   - Example: bare "opus" with default profile "top"

5. Phase 3: Profile Alias Lookup
   - Exact-match (case-insensitive) within profile.aliases
   - Differs from AliasManager's substring matching

6. Phase 4: Literal Model Bypass (! prefix)
   - !my-model bypasses substring matching
   - Still allows provider normalization
   - Use case: exact model names that overlap with aliases

7. Phase 5: AliasManager Resolution
   - Resolver chain: LiteralPrefix -> ChainedAlias -> SubstringMatcher -> MatchRanker
   - CORRECTED match priority:
     exact > longest substring > default-target provider preference > provider alphabetical > alias alphabetical
   - Chained resolution (up to 10 levels with cycle detection)
   - Provider-scoped vs cross-provider

8. Phase 6: Provider Prefix Parsing
   - "provider:model" syntax
   - Default target fallback

9. Phase 7: Final Result
   - (provider, model) tuple
   - Debug logging output

10. Configuration Quick Reference
    - Single table: What | Where | Example
    - Env vars, TOML, profiles

11. End-to-End Examples
    - 8-10 "What happens when..." traces through the full pipeline

12. Troubleshooting
    - Common confusion points
    - Debugging with LOG_LEVEL=DEBUG

Appendix A: AliasManager Architecture (for developers)
  - Resolver chain internals
  - Caching mechanism (TTL + generation-based invalidation)
  - MatchRanker algorithm detail

Appendix B: TOML Configuration Syntax
  - Full syntax reference
```

### 2. Fix inconsistencies

| File | Fix |
|------|-----|
| `docs/model-aliases.md` | Add cross-reference to model-resolution.md at top. Fix MatchRanker priority. Fix fallback alias tables (add OpenAI + Anthropic columns). |
| `docs/fallback-aliases.md` | Add cross-reference. Add OpenAI + Anthropic fallbacks. Mention `[defaults.aliases]` global fallbacks. |
| `CLAUDE.md` | Add link to model-resolution.md in "Using Model Aliases" section. Fix MatchRanker priority if mentioned. |

### 3. Wire references

| File | Change |
|------|--------|
| `CLAUDE.md` | "Using Model Aliases" section: add `> For the full resolution pipeline, see docs/model-resolution.md` |
| `README.md` | Add "Model Resolution" subsection linking to the guide |
| `docs/model-aliases.md` | Add note at top linking to model-resolution.md |
| `docs/fallback-aliases.md` | Add note at top linking to model-resolution.md |
| `docs/provider-routing-guide.md` | Add link in routing section |

### 4. Fix docstring

Expand `ModelManager.resolve_model()` docstring from 5 vague steps to the actual 7 phases:

```
1. Profile prefix detection — "profile:model" → strip prefix, use profile
2. Default profile inheritance — bare name + default is profile → set profile
3. Profile alias lookup — exact-match in profile.aliases
4. Literal model bypass — "!model" → skip substring matching
5. AliasManager resolution — substring, chained, ranked
6. Provider prefix parsing — "provider:model" or default target
7. Return (provider, actual_model)
```

## Task Breakdown

1. Create `docs/model-resolution.md` with full content
2. Fix `docs/model-aliases.md` (MatchRanker priority, tables, cross-reference)
3. Fix `docs/fallback-aliases.md` (tables, cross-reference)
4. Wire references in CLAUDE.md, README.md, provider-routing-guide.md
5. Fix `ModelManager.resolve_model()` docstring
