# Model Name Resolution Guide

> This is the authoritative reference for how Vandamme Proxy resolves model names.
> For configuration syntax, see [Model Aliases Configuration](model-aliases.md).
> For fallback defaults, see [Fallback Aliases](fallback-aliases.md).

## Overview

Every request to Vandamme Proxy includes a model name. The proxy resolves that name
through a **7-phase pipeline** to determine which provider and which actual model to
use. This guide walks through each phase with examples.

The resolution is implemented in `src/core/model_manager.py` (`ModelManager.resolve_model()`).

## The Resolution Pipeline

When you send a model name (e.g., `"opus"`, `"openai:gpt-4o"`, `"top:haiku"`),
it passes through these phases **in order**. The first phase that produces a match
determines the outcome.

```
Input: "model-name"
  |
  +-- Contains ":" ?
  |   +-- yes: Is prefix a profile? --yes--> Phase 1: Use profile, strip prefix
  |   |                                  no--> Skip to Phase 4
  |   +-- no: Default target is a profile? --yes--> Phase 2: Set profile from default
  |          no--> (profile = None)
  |
  +-- Profile active AND exact alias match? --yes--> Phase 3: Use profile alias
  |
  +-- Model starts with "!"? --yes--> Phase 4: Literal bypass
  |
  +-- Phase 5: AliasManager resolution (substring, chained, ranked)
  |   +-- Alias found? --yes--> Use resolved value
  |   +-- no--> Pass model through unchanged
  |
  +-- Phase 6: Parse provider prefix from resolved model
  |   +-- Has "provider:" prefix? --yes--> (provider, model)
  |   +-- no--> (default_target, model)
  |
  Phase 7: Return (provider, actual_model)
```

### Phase Summary

| Phase | Name | What happens | Input example | Output |
|-------|------|-------------|---------------|--------|
| 1 | Profile prefix | Detect `"profile:model"` syntax; profiles win over providers | `"top:opus"` | profile=`top`, model=`"opus"` |
| 2 | Default profile | Bare name + `VDM_DEFAULT_TARGET` is a profile | `"opus"` (default=`top`) | profile=`top`, model=`"opus"` |
| 3 | Profile aliases | Exact-match (case-insensitive) in `profile.aliases` | `"opus"` (profile has `opus` -> `opencodego:kimi-k2.6`) | `"opencodego:kimi-k2.6"` |
| 4 | Literal bypass | `!` prefix skips substring matching | `"!my-exact-model"` | `"my-exact-model"` (no substring) |
| 5 | AliasManager | Substring match, chained resolution, ranked by priority | `"haiku"` | `"zai:GLM-4.7-Flash"` (via chain) |
| 6 | Provider prefix | Parse `"provider:model"` or fall back to default target | `"openai:gpt-4o"` | provider=`openai`, model=`gpt-4o` |
| 7 | Final | Return tuple | -- | `("zai", "GLM-4.7-Flash")` |

Phases 4-7 are covered in a [later section](#phases-4-7-detailed).

---

## Phase 1: Profile Prefix Detection

When the model string contains a colon (`:`), the proxy checks whether the part
before the colon is a **profile name** (not a provider name).

```python
# src/core/model_manager.py:69-76
if ":" in model:
    potential_profile, model_part = model.split(":", 1)
    if profile_manager and profile_manager.is_profile(potential_profile):
        profile = profile_manager.get_profile(potential_profile)
        model = model_part  # strip the profile prefix
```

### How it works

1. Split the model string on the first `:` to get a potential prefix.
2. Ask the `ProfileManager` whether that prefix is a known profile.
3. If yes: record the profile and strip the prefix, continuing with the remainder.
4. If no: leave `profile = None`. The model retains its `:` prefix, so Phase 2
   is skipped (it only applies to bare names). The model continues through
   Phase 4/5 logic with the colon intact, and Phase 6 parses it as a
   provider prefix.

### Profiles take precedence over providers (intentional)

When a profile name matches a provider name (case-insensitive), the profile wins.
This is a deliberate feature that allows custom provider overrides.

For example, if you define a profile named `"openai"` in TOML:

```toml
[profiles.openai]
timeout = 120
[profiles.openai.aliases]
haiku = "anthropic:claude-3-5-haiku-20241022"  # Override to use Anthropic
```

Then a request with `"openai:haiku"` resolves through the **profile**, not the
provider. The proxy logs a message when profile names collide with provider names
(see `ProfileManager.detect_collisions()`).

### Examples

| Input | Profile exists? | Result |
|-------|----------------|--------|
| `"top:opus"` | `top` is a profile | profile=`top`, model=`"opus"` -> Phase 3 |
| `"main:haiku"` | `main` is a profile | profile=`main`, model=`"haiku"` -> Phase 3 |
| `"openai:gpt-4o"` | `openai` is NOT a profile | profile=`None`, no prefix stripped -> Phase 5/6 |
| `"webdev:haiku"` | `webdev` is NOT a profile | profile=`None`, no prefix stripped -> Phase 5/6 |

---

## Phase 2: Default Profile Inheritance

When the model string has **no colon** and **does not start with `!`**, the proxy
checks whether the configured default target (`VDM_DEFAULT_TARGET`) is a profile
name. If so, that profile is applied automatically to bare model names.

```python
# src/core/model_manager.py:80-91
if profile is None and ":" not in model and not model.startswith("!"):
    default_profile_name = self.provider_manager.default_profile
    if default_profile_name:
        profile = profile_manager.get_profile(default_profile_name)
```

### Why this exists

The default target (`VDM_DEFAULT_TARGET`) can be either a provider name or a profile
name. When it is a profile, the proxy still needs a real provider for actual API
routing. The `DefaultProviderSelector` handles this split:

- `default_target` property always returns a **real provider name** after
  provider initialization (backward compatible with code that needs a provider).
  Before initialization, it may return the raw configured value (which could be
  a profile name).
- `default_profile` property returns the **profile name** separately (e.g., `"top"`),
  or `None` if the default target is a provider.

This means `VDM_DEFAULT_TARGET=top` (the default in `defaults.toml`) activates the
`top` profile's aliases for all bare model names, while the actual API routing
falls back to the first available provider.

### Conditions for activation

All three must be true:

1. No explicit profile prefix was found in Phase 1 (`profile is None`).
2. The model string contains no `:` (not already provider-prefixed).
3. The model string does not start with `!` (not a literal bypass).

### Examples

Assume `VDM_DEFAULT_TARGET=top` (the default in `defaults.toml`):

| Input | Phase 2 activates? | Result |
|-------|-------------------|--------|
| `"opus"` | Yes (bare name, no `:`, no `!`) | profile=`top`, model=`"opus"` -> Phase 3 |
| `"haiku"` | Yes | profile=`top`, model=`"haiku"` -> Phase 3 |
| `"openai:gpt-4o"` | No (has `:`) | profile=`None` -> Phase 5/6 |
| `"!my-model"` | No (starts with `!`) | profile=`None` -> Phase 4 |

If `VDM_DEFAULT_TARGET=openai` (a provider, not a profile), Phase 2 never
activates because `default_profile` returns `None`.

---

## Phase 3: Profile Alias Lookup

When a profile is active (from Phase 1 or Phase 2), the proxy checks whether the
model name matches an alias **exactly** (case-insensitive) in that profile's alias
map.

```python
# src/core/model_manager.py:97-99
if profile and model.lower() in profile.aliases:
    resolved_model = profile.aliases[model.lower()]
```

### Exact match only (case-insensitive)

Profile aliases use **exact matching**, unlike the AliasManager's substring matching.
The model name must match an alias key character-for-character (ignoring case).

| Model input | Profile `top.aliases` has `opus`? | Match? | Why |
|-------------|-----------------------------------|--------|-----|
| `"opus"` | `opus = "opencodego:kimi-k2.6"` | Yes | Exact match |
| `"OpUs"` | `opus = "opencodego:kimi-k2.6"` | Yes | Case-insensitive |
| `"opus-v2"` | `opus = "opencodego:kimi-k2.6"` | **No** | Not an exact match |
| `"op"` | `opus = "opencodego:kimi-k2.6"` | **No** | Substring does not match |

### Fallthrough behavior

If no exact profile alias match is found, the model falls through to **Phase 5**
(AliasManager). The profile is still recorded but has no effect on alias resolution.

### Real examples from defaults.toml

The `top` profile (the default) has these aliases:

```toml
[profiles.top.aliases]
haiku = "zai:haiku"
sonnet = "zai:sonnet"
opus = "opencodego:kimi-k2.6"
long = "opencodego:mimo-v2.5-pro"
personalagent = "zai:personalagent"
```

The `main` profile has these aliases:

```toml
[profiles.main.aliases]
haiku = "zai:haiku"
sonnet = "poe:gemini-flash"
opus = "agentrouter:opus"
```

Resolution examples with default profile `top`:

| Input | Profile alias match | Resolved model | Next phase |
|-------|-------------------|----------------|------------|
| `"opus"` | `opus` -> `"opencodego:kimi-k2.6"` | `"opencodego:kimi-k2.6"` | Phase 6 |
| `"haiku"` | `haiku` -> `"zai:haiku"` | `"zai:haiku"` | Phase 6 |
| `"unknown-model"` | No match | `"unknown-model"` (unchanged) | Phase 5 |
| `"long"` | `long` -> `"opencodego:mimo-v2.5-pro"` | `"opencodego:mimo-v2.5-pro"` | Phase 6 |

In the default configuration, profile alias targets contain a provider prefix
(e.g., `"zai:haiku"`), so after Phase 3, the model typically goes directly to
Phase 6. If a profile alias target lacks a provider prefix, it falls through to
Phase 5 instead.

---

## Phases 4-7 (Detailed)

> Phases 4 through 7 are covered in a [separate section](#phases-4-7-detailed).
> They handle literal bypass, AliasManager resolution, provider prefix parsing,
> and the final result.

*(To be expanded in a subsequent update.)*
