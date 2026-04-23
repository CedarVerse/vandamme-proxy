# Model Resolution Documentation Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Create a unified model resolution guide and fix all documentation inconsistencies so users understand exactly what happens when they type a model name.

**Architecture:** Single new authoritative guide (`docs/model-resolution.md`) with pipeline-first structure, cross-referenced from all existing docs. Existing docs get targeted fixes for inaccuracies.

**Tech Stack:** Markdown documentation, Python docstrings

---

### Task 0: Create `docs/model-resolution.md` — Sections 1-3 (Overview, Pipeline Diagram, Profile Prefix)

**Files:**
- Create: `docs/model-resolution.md`

**Step 1: Create the file with the front matter and overview**

```markdown
# Model Name Resolution Guide

> This is the authoritative reference for how Vandamme Proxy resolves model names.
> For configuration syntax, see [Model Aliases Configuration](model-aliases.md).
> For fallback defaults, see [Fallback Aliases](fallback-aliases.md).

## Overview

Every request to Vandamme Proxy includes a model name. The proxy resolves that name
through a 7-phase pipeline to determine which provider and which actual model to use.
This guide walks through each phase with examples.

## The Resolution Pipeline

When you send a model name (e.g., `"opus"`, `"openai:gpt-4o"`, `"top:haiku"`),
it passes through these phases **in order**. The first phase that produces a match wins.

```
Input: "model-name"
  │
  ├─ Contains ":" ?
  │   ├─ yes: Is prefix a profile? ──yes──> Phase 1: Use profile, strip prefix
  │   │                                  no──> Skip to Phase 4
  │   no──> Default target is a profile? ──yes──> Phase 2: Set profile from default
  │   no──> (profile = None)
  │
  ├─ Profile active AND exact alias match? ──yes──> Phase 3: Use profile alias
  │
  no──> Model starts with "!"? ──yes──> Phase 4: Literal bypass
  │
  no──> Phase 5: AliasManager resolution (substring, chained, ranked)
  │   ├─ Alias found? ──yes──> Use resolved value
  │   no──> Pass model through unchanged
  │
  Phase 6: Parse provider prefix from resolved model
  ├─ Has "provider:" prefix? ──yes──> (provider, model)
  no──> (default_target, model)
  │
  Phase 7: Return (provider, actual_model)
```

| Phase | What happens | Input example | Output |
|-------|-------------|---------------|--------|
| 1. Profile prefix | Detect `"profile:model"` syntax | `"top:opus"` | profile=top, model="opus" |
| 2. Default profile | Bare name + default is profile | `"opus"` (VDM_DEFAULT_TARGET=top) | profile=top, model="opus" |
| 3. Profile aliases | Exact-match in profile.aliases | `"opus"` (profile has opus→kimi-k2.6) | `"opencodego:kimi-k2.6"` |
| 4. Literal bypass | `!` prefix skips substring matching | `"!my-exact-model"` | `"my-exact-model"` (no substring) |
| 5. AliasManager | Substring + chained + ranked | `"haiku"` | `"poe:grok-4.1-fast-non-reasoning"` |
| 6. Provider prefix | Parse `"provider:model"` | `"openai:gpt-4o"` | provider=openai, model=gpt-4o |
| 7. Final | Return tuple | — | `("poe", "grok-4.1-fast-non-reasoning")` |
```

**Step 2: Add Phase 1 — Profile Prefix Detection section**

Write a section explaining `"profile:model"` syntax:
- When the model string contains `:`, check if the part before `:` is a profile name
- Profiles take precedence over providers when names collide (intentional feature)
- Example: `"webdev-good:haiku"` → profile "webdev-good" is used, prefix is stripped
- Example: `"openai:haiku"` where "openai" is a profile → profile wins (collision feature)
- Example: `"openai:gpt-4o"` where "openai" is NOT a profile → treated as provider prefix (Phase 6)

**Step 3: Add Phase 2 — Default Profile Inheritance section**

Write a section explaining bare model default profile:
- When `VDM_DEFAULT_TARGET` is set to a profile name (e.g., `"top"`), bare model names automatically use that profile's aliases
- This only applies to bare names (no `:` prefix, no `!` prefix)
- Example: `VDM_DEFAULT_TARGET=top` + model `"opus"` → profile "top" is used automatically
- The `default_target` property still returns a real provider name (backward compatible)
- The `default_profile` property returns `"top"` separately

**Step 4: Add Phase 3 — Profile Alias Lookup section**

Write a section explaining profile alias matching:
- **Exact match only** (case-insensitive) — unlike AliasManager's substring matching
- The alias map is defined in TOML: `[profiles.name.aliases]`
- Example: profile "top" with `aliases = { opus = "opencodego:kimi-k2.6" }` → `"opus"` resolves exactly
- If no exact match: falls through to Phase 5 (AliasManager)

**Step 5: Commit**

```
hug a docs/model-resolution.md
hug commit -m "docs: start model resolution guide (phases 1-3)"
```

---

### Task 1: Add Phases 4-7 and examples to `docs/model-resolution.md`

**Files:**
- Modify: `docs/model-resolution.md`

**Step 1: Add Phase 4 — Literal Model Bypass section**

Explain the `!` prefix:
- Prefixing a model name with `!` bypasses substring matching
- Use case: you have an alias `"fast"` but want to use a model literally named `"fast-chat"`
- `!fast-chat` → uses "fast-chat" as-is (AliasManager only normalizes provider prefix)
- Without `!`: `"fast-chat"` might match the `"fast"` alias via substring
- Still allows provider normalization: `!my-model` with default target "openai" → `"openai:my-model"`

**Step 2: Add Phase 5 — AliasManager Resolution section**

This is the most detailed section. Cover:

- **The resolver chain**: LiteralPrefixResolver → ChainedAliasResolver → SubstringMatcher → MatchRanker
- **Match priority** (CORRECTED from previous docs):
  1. Exact match over substring
  2. Longer alias over shorter
  3. **Default-target provider preference** (undocumented in previous docs)
  4. Provider name alphabetical
  5. Alias name alphabetical
- **Chained resolution**: aliases can point to other aliases, resolved up to 10 levels with cycle detection
  - Example: `fast → sonnet → gpt-4o-mini` (follows the chain)
- **Provider-scoped vs cross-provider**:
  - No `:` in model → scoped to default provider only
  - Has `:` in model → cross-provider search

**Step 3: Add Phase 6 — Provider Prefix Parsing section**

- `"provider:model"` → `(provider, model)`
- No prefix → `(default_target, model)`
- Default target comes from `VDM_DEFAULT_TARGET` env var or TOML config

**Step 4: Add Phase 7 — Final Result section**

- Returns `(provider_name, actual_model_name)` tuple
- Debug logging: set `LOG_LEVEL=DEBUG` to see each phase in action
- Example log output showing the full trace

**Step 5: Add End-to-End Examples section**

8-10 "What happens when..." examples tracing through the full pipeline:

1. `claude --model opus` with VDM_DEFAULT_TARGET=top → Phase 2+3 → profile alias
2. `claude --model top:opus` → Phase 1+3 → explicit profile prefix
3. `claude --model openai:gpt-4o` → Phase 1 (not profile) → Phase 5 (no alias) → Phase 6
4. `claude --model haiku` with VDM_DEFAULT_TARGET=poe → Phase 5 → AliasManager substring match
5. `claude --model !my-exact-model` → Phase 4 → literal bypass
6. `claude --model fast-chat` where alias "fast" exists → Phase 5 → substring match
7. `claude --model opus` with VDM_DEFAULT_TARGET=openai (not a profile) → Phase 5 → fallback alias
8. `claude --model webdev-good:unknown` → Phase 1 (profile) → Phase 3 (no alias) → Phase 5+6

**Step 6: Add Configuration Quick Reference section**

Single table:
| What | Where | Example |
|------|-------|---------|
| Provider alias | `{PROVIDER}_ALIAS_{NAME}` env var | `POE_ALIAS_HAIKU=grok-4.1-fast` |
| Profile | `vandamme-config.toml [profiles.name]` | `[profiles.top]` with `[profiles.top.aliases]` |
| Default target | `VDM_DEFAULT_TARGET` env var | `VDM_DEFAULT_TARGET=top` |
| Fallback aliases | `defaults.toml [defaults.aliases]` | See fallback-aliases.md |
| TOML provider aliases | `vandamme-config.toml [provider.aliases]` | `[poe.aliases] haiku = "grok-4.1-fast"` |

**Step 7: Add Troubleshooting section**

Common issues:
- "My alias isn't matching" → check case-insensitivity, substring matching, provider scope
- "Wrong provider selected" → check VDM_DEFAULT_TARGET, provider prefix, MatchRanker priority
- "Profile aliases ignored" → check profile is the default target, bare model (no prefix)
- Debug: `LOG_LEVEL=DEBUG` to see each resolution phase

**Step 8: Add Appendix A — AliasManager Architecture (for developers)**

Cover:
- ResolutionContext and ResolutionResult data classes
- The four resolver components and their roles
- AliasResolverCache (TTL + generation-based invalidation)
- MatchRanker sort key detail (the exact 5-tuple)

**Step 9: Commit**

```
hug a docs/model-resolution.md
hug commit -m "docs: complete model resolution guide (phases 4-7, examples, appendix)"
```

---

### Task 2: Fix `docs/model-aliases.md` — MatchRanker priority and tables

**Files:**
- Modify: `docs/model-aliases.md`

**Step 1: Add cross-reference at the top**

After the title and overview, add:

```markdown
> **See also:** [Model Name Resolution Guide](model-resolution.md) — the complete pipeline from input to output.
```

**Step 2: Fix the match priority**

Find any mention of match priority (search for "exact match", "longest", "alphabetical") and correct it to:

```
1. Exact match over substring match
2. Longer alias over shorter (more specific wins)
3. Default-target provider preference (the provider matching VDM_DEFAULT_TARGET wins ties)
4. Provider name, alphabetical (e.g., "anthropic" before "openai")
5. Alias name, alphabetical (final tiebreaker)
```

Note the **new item 3**: default-target provider preference. This was missing from all docs.

**Step 3: Fix the Built-in Fallback Aliases table**

Currently only shows Poe provider. Replace with the full three-provider table from CLAUDE.md:

| Special Name | Poe Provider | OpenAI Provider | Anthropic Provider |
|--------------|-------------|-----------------|-------------------|
| `haiku` | `grok-4.1-fast-non-reasoning` | `gpt-5.1-mini` | `claude-3-5-haiku-20241022` |
| `sonnet` | `glm-4.6` | `gpt-5.1-codex` | `claude-3-5-sonnet-20241022` |
| `opus` | `gpt-5.2` | `gpt-5.2` | `claude-3-opus-20240229` |

**Step 4: Commit**

```
hug a docs/model-aliases.md
hug commit -m "docs: fix match priority and fallback tables in alias guide"
```

---

### Task 3: Fix `docs/fallback-aliases.md` — tables and cross-reference

**Files:**
- Modify: `docs/fallback-aliases.md`

**Step 1: Add cross-reference at the top**

```markdown
> **See also:** [Model Name Resolution Guide](model-resolution.md) — how fallback aliases fit into the full resolution pipeline.
```

**Step 2: Fix the Default Fallback Mappings table**

Add OpenAI and Anthropic columns to match the corrected table from Task 2. Also mention `[defaults.aliases]` global fallbacks from TOML config.

**Step 3: Commit**

```
hug a docs/fallback-aliases.md
hug commit -m "docs: expand fallback aliases to all providers, add cross-reference"
```

---

### Task 4: Wire cross-references in CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/provider-routing-guide.md` (if it exists)

**Step 1: Add link in CLAUDE.md**

At line 543 (the "Using Model Aliases" section header area), add after the intro sentence:

```markdown
> For the complete model resolution pipeline (how bare names, profiles, and aliases interact), see [Model Resolution Guide](docs/model-resolution.md).
```

**Step 2: Add section in README.md**

After the "Smart Model Aliases" feature bullet (around line 67), or after the request flow section (around line 125), add a brief subsection:

```markdown
### Model Resolution

Every model name passes through a 7-phase resolution pipeline: profile prefix → default profile → profile aliases → literal bypass → AliasManager → provider prefix → final result.

For the full guide with examples, see [Model Resolution](docs/model-resolution.md).
```

**Step 3: Add link in provider-routing-guide.md**

If `docs/provider-routing-guide.md` exists, add a cross-reference in the routing section:

```markdown
> For how model names are resolved (aliases, profiles, provider selection), see [Model Resolution Guide](model-resolution.md).
```

**Step 4: Commit**

```
hug a CLAUDE.md README.md docs/provider-routing-guide.md
hug commit -m "docs: wire model resolution cross-references in CLAUDE.md and README"
```

---

### Task 5: Fix `ModelManager.resolve_model()` docstring

**Files:**
- Modify: `src/core/model_manager.py:52-64`

**Step 1: Replace the docstring**

Current (vague 5-step):
```python
    """Resolve model name to (provider, actual_model)

    Resolution process:
    1. Check for profile prefix (profiles take precedence over providers)
    2. If profile prefix, use profile's aliases for resolution
    3. Otherwise, use existing alias resolution logic
    4. Parse provider prefix from resolved value
    5. Return provider and actual model name

    Returns:
        Tuple[str, str]: (provider_name, actual_model_name)
    """
```

Replace with accurate 7-phase docstring:
```python
    """Resolve model name to (provider, actual_model).

    The resolution pipeline runs these phases in order (first match wins):

    1. Profile prefix: "profile:model" → detect profile, strip prefix
    2. Default profile: bare name + VDM_DEFAULT_TARGET is a profile → set profile
    3. Profile aliases: exact-match (case-insensitive) in profile.aliases
    4. Literal bypass: "!model" → skip substring matching
    5. AliasManager: substring match, chained resolution, ranked by priority
    6. Provider prefix: "provider:model" or default target fallback
    7. Return (provider_name, actual_model_name)

    See docs/model-resolution.md for the full guide with examples.

    Returns:
        Tuple[str, str]: (provider_name, actual_model_name)
    """
```

**Step 2: Commit**

```
hug a src/core/model_manager.py
hug commit -m "docs: expand resolve_model() docstring to 7-phase pipeline"
```

---

### Task 6: Final review

**Step 1: Verify all cross-references resolve**

```bash
# Check all markdown links in the new guide
grep -o '\[.*\](.*)' docs/model-resolution.md
# Verify referenced files exist
ls docs/model-aliases.md docs/fallback-aliases.md docs/provider-routing-guide.md
```

**Step 2: Verify consistency**

- Fallback alias tables match across CLAUDE.md, docs/model-aliases.md, docs/fallback-aliases.md
- MatchRanker priority documented identically in docs/model-resolution.md and docs/model-aliases.md
- resolve_model() docstring phases match the guide's phases

**Step 3: Run existing tests to ensure no code regressions**

```bash
make test-unit
```

**Step 4: Commit any fixes**

If inconsistencies found, fix and commit.
