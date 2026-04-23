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

## Phase 4: Literal Model Bypass

Prefixing a model name with `!` tells the proxy to skip **substring matching** in
AliasManager (Phase 5). The model name is used as-is, with only provider prefix
normalization applied.

### When to use it

Substring matching can cause surprises when a short alias name is a substring of
a real model you want to use. For example, if you have an alias `fast` pointing
to `grok-4.1-fast-non-reasoning`, then a model literally named `"fast-chat"`
would match that alias instead of being used directly.

The `!` prefix prevents this:

| Input | Without `!` | With `!` |
|-------|-------------|----------|
| `"fast-chat"` | Matches alias `fast` -> resolved | `!fast-chat` -> used literally as `fast-chat` |
| `"haiku-3"` | Matches alias `haiku` -> resolved | `!haiku-3` -> used literally as `haiku-3` |

### What `!` does and does not do

```python
# src/core/model_manager.py:103-110
if model.startswith("!"):
    if ":" not in model:
        # No provider prefix — normalize using default target
        resolved_model = alias_manager.resolve_alias(model, provider=default_target) or model
    else:
        # Has provider prefix — normalize using explicit provider
        resolved_model = alias_manager.resolve_alias(model) or model
```

**Does:**
- Strip the `!` prefix and pass the remainder to the resolver chain.
- `LiteralPrefixResolver` (priority 10) catches it first and returns a
  `was_resolved=False` result with the provider-prefixed model name.
- Still applies **provider prefix normalization**: `!my-model` with default
  target `top` (profile, falls back to first provider) -> `<provider>:my-model`.

**Does NOT:**
- Skip Phase 6 (provider prefix parsing). The final `:` is still parsed.
- Affect Phase 1-3 (profile handling). Profile prefix + `!` works fine:
  `top:!my-model` -> Phase 1 strips profile, Phase 4 sees `!my-model`.

### Interaction with profiles

| Input | Phase 1 | Phase 4 | Result |
|-------|---------|---------|--------|
| `top:!my-model` | Profile `top`, model=`!my-model` | Literal bypass | `top`'s default provider + `my-model` |
| `!top:opus` | `!top` is not a profile -> no strip | Literal bypass, provider=`!top` | **Misinterpreted** -- avoid this syntax |

**Tip:** Always put the `!` after the profile prefix: `top:!my-model`, not
`!top:my-model`. The latter treats `!top` as a provider name.

---

## Phase 5: AliasManager Resolution

This is the core of model name resolution. When no profile alias matched (or no
profile is active), the `AliasManager` takes over. It runs a **resolver chain**
of four components in priority order.

### The resolver chain

```
Input model (e.g., "haiku", "openai:gpt-4o", "fast-chat")
  |
  v
[1] LiteralPrefixResolver (priority 10)
  |  Already handled in Phase 4 at the ModelManager level.
  |  Still in the chain for direct AliasManager consumers.
  |
[2] ChainedAliasResolver (priority 20)
  |  Handles "provider:model" where model is itself an alias.
  |  Follows chains up to 10 levels with cycle detection.
  |
[3] SubstringMatcher (priority 30)
  |  Case-insensitive substring matching against alias names.
  |  Creates underscore/hyphen variations.
  |  Stores all matches for the MatchRanker.
  |
[4] MatchRanker (priority 40)
     Ranks matches by a 5-tuple sort key and picks the best.
```

### Match priority (the 5-tuple sort key)

When multiple aliases match a model name, `MatchRanker` sorts them by this tuple
(lower values win):

```python
# src/core/alias/resolver.py:414-421
matches.sort(key=lambda m: (
    0 if m.is_exact else 1,                          # 1. Exact match first
    -m.length,                                        # 2. Longer alias first
    0 if m.provider == context.default_target else 1, # 3. Default-target provider first
    m.provider,                                       # 4. Provider name alphabetical
    m.alias,                                          # 5. Alias name alphabetical
))
```

**Breakdown:**

| Priority | Criterion | Example |
|----------|-----------|---------|
| 1 | Exact match over substring | `haiku` beats `hai` when input is `haiku` |
| 2 | Longer alias over shorter | `extract2` beats `extract` when input is `extract2-special` |
| 3 | Default-target provider preference | If `VDM_DEFAULT_TARGET=top` (profile), falls back to first provider |
| 4 | Provider name alphabetical | `anthropic` before `poe` before `zai` |
| 5 | Alias name alphabetical | `fast` before `fast-chat` |

**Priority 3 is subtle but important:** When two aliases match equally well (same
exactness, same length), the one from the default-target provider wins. This is
why setting `VDM_DEFAULT_TARGET=poe` causes `haiku` to resolve to `gpt-5.1-mini`
(Poe's haiku) instead of `GLM-4.7-Flash` (ZAI's haiku) -- when both are equal
matches and the default target is a real provider.

### Chained resolution

Aliases can point to other aliases. The `ChainedAliasResolver` follows these
chains up to 10 levels, with cycle detection to prevent infinite loops.

**Example chain** (using `defaults.toml` values):

```
"haiku" (defaults.aliases) -> "zai:haiku"
  -> (zai.aliases) "GLM-4.7-Flash"     [final value]
```

```
"opus" (defaults.aliases) -> "opencodego:kimi-k2.6"
  -> (opencodego.aliases) no "kimi-k2.6" alias  [stops here, uses literal]
```

```
"fast" (poe.aliases) -> "grok-4.1-fast-non-reasoning"
  -> (poe.aliases) no "grok-4.1-fast-non-reasoning" alias  [stops here]
```

**Chain behavior:**
- Max 10 iterations before stopping with a warning.
- Cycle detection: if `a -> b -> a` is detected, the last successfully resolved
  value is returned.
- Chain resolution only applies when the model contains `:` (i.e., it has a
  provider prefix or was already resolved to one).

### Provider scoping (critical detail)

> **CORRECTION:** Previous versions of this documentation incorrectly described
> `:` as triggering cross-provider resolution. This is wrong -- `:` always scopes
> to a single provider.

The `:` in a model name always **scopes** resolution to the named provider -- it
does NOT trigger a cross-provider search.

```python
# src/core/model_manager.py:117-125
if ":" not in model:
    # No provider prefix — scope to default target only
    alias_target = alias_manager.resolve_alias(model, provider=default_target)
else:
    # Has provider prefix — resolve with provider=None
    # SubstringMatcher extracts the explicit provider from the model string
    alias_target = alias_manager.resolve_alias(model)
```

The `SubstringMatcher` then uses the extracted provider for scoping:

```python
# src/core/alias/resolver.py:328-336
explicit_provider = model_lower.split(":", 1)[0] if ":" in model_lower else None
search_provider = explicit_provider or (context.provider.lower() if context.provider else None)

for provider_name, provider_aliases in context.aliases.items():
    if search_provider and provider_name != search_provider:
        continue  # Skip providers that don't match
```

**Summary table:**

| Model input | Search scope | Why |
|-------------|-------------|-----|
| `"haiku"` | Default target's aliases only | No `:`, `provider` param set to default target |
| `"poe:haiku"` | Poe's aliases only | `:` extracts `poe` as `search_provider` |
| `"openai:haiku"` | OpenAI's aliases only | `:` extracts `openai` as `search_provider` |

**Cross-provider resolution only happens through alias chain targets.** For
example, `defaults.toml` has `haiku = "zai:haiku"` in `[defaults.aliases]`. When
this alias is matched, the target `"zai:haiku"` contains a different provider
(`zai`) than the original scope. The `ChainedAliasResolver` then follows this
to the `zai` provider's aliases, resolving to `GLM-4.7-Flash`.

### Substring matching direction

The matching checks whether an **alias name is a substring of the input model**:

| Alias | Input model | Match? | Why |
|-------|-------------|--------|-----|
| `fast` | `fast-chat` | Yes | `fast` is a substring of `fast-chat` |
| `fast-chat` | `fast` | **No** | `fast-chat` is NOT a substring of `fast` |
| `haiku` | `haiku` | Yes (exact) | Equal strings |
| `haiku` | `HAIKU` | Yes (exact) | Case-insensitive |
| `haiku` | `haiku_3` | Yes | `haiku` is a substring of `haiku_3` |
| `haiku` | `haiku-3` | Yes | Hyphen/underscore variations are created |

The `SubstringMatcher` creates three variations of the input: the original,
one with underscores replaced by hyphens, and one with hyphens replaced by
underscores. Each alias is then checked against all three variations.

---

## Phase 6: Provider Prefix Parsing

After all alias resolution is complete, the resolved model string is parsed to
extract the provider name and the actual model name.

```python
# src/core/model_manager.py:136-138
provider_name, actual_model = self.provider_manager.parse_model_name(resolved_model)
```

### Parsing rules

| Resolved model | Provider | Actual model |
|----------------|----------|--------------|
| `"openai:gpt-4o"` | `openai` | `gpt-4o` |
| `"zai:GLM-4.7-Flash"` | `zai` | `GLM-4.7-Flash` |
| `"gpt-4o"` (no prefix) | default target | `gpt-4o` |

The default target comes from:
1. `VDM_DEFAULT_TARGET` environment variable (highest priority).
2. `default-target` in TOML config files (project > user > defaults.toml).
3. Falls back to the first configured provider.

When the default target is a **profile** (e.g., `top`), the `DefaultProviderSelector`
resolves it to a real provider name for actual API routing. This happens
transparently -- the profile's settings (timeout, retries) are applied, but the
API call goes to a real provider.

---

## Phase 7: Final Result

The resolution pipeline returns a `(provider_name, actual_model_name)` tuple.
This tuple is used to route the request to the correct provider with the correct
model name.

### Debug logging

Set `LOG_LEVEL=DEBUG` to see each phase in action. Example output for
`claude --model haiku` with `VDM_DEFAULT_TARGET=top`:

```
DEBUG [model_manager] Starting model resolution for: 'haiku'
DEBUG [model_manager] Using default profile 'top' for bare model resolution
DEBUG [model_manager] Profile alias resolved: 'haiku' -> 'zai:haiku'
DEBUG [model_manager] Parsing provider prefix from resolved model: 'zai:haiku'
DEBUG [model_manager] Parsed provider: 'zai', actual model: 'haiku'
DEBUG [model_manager] Resolved: 'haiku' -> 'zai:haiku' (via profile alias)
```

Example for `claude --model poe:haiku` (explicit provider prefix, no profile):

```
DEBUG [model_manager] Starting model resolution for: 'poe:haiku'
DEBUG [model_manager] Alias manager available with 47 aliases
DEBUG [model_manager] Resolving alias 'poe:haiku' across all providers
DEBUG [alias.resolver.SubstringMatcher] model_for_match='haiku', search_provider='poe'
DEBUG [alias.resolver.MatchRanker] (exact match for 'poe:haiku') 'poe:haiku' -> 'poe:gpt-5.1-mini'
DEBUG [model_manager] Alias resolved: 'poe:haiku' -> 'poe:gpt-5.1-mini'
DEBUG [model_manager] Parsing provider prefix from resolved model: 'poe:gpt-5.1-mini'
DEBUG [model_manager] Parsed provider: 'poe', actual model: 'gpt-5.1-mini'
```

Example for `claude --model !my-exact-model` (literal bypass):

```
DEBUG [model_manager] Starting model resolution for: '!my-exact-model'
DEBUG [alias.resolver.LiteralPrefixResolver] Literal: '!my-exact-model' -> 'zai:my-exact-model'
DEBUG [model_manager] Parsing provider prefix from resolved model: 'zai:my-exact-model'
DEBUG [model_manager] Parsed provider: 'zai', actual model: 'my-exact-model'
```

---

## End-to-End Examples

Each example traces through the full 7-phase pipeline. All use the default
`VDM_DEFAULT_TARGET=top` unless stated otherwise.

### Example 1: `claude --model opus`

**Configuration:** `VDM_DEFAULT_TARGET=top` (default)

```
Phase 1: "opus" has no ":" -> skip
Phase 2: default target "top" IS a profile -> profile = top
Phase 3: "opus" matches top.aliases["opus"] = "opencodego:kimi-k2.6"
Phase 4-5: skipped (profile alias resolved)
Phase 6: "opencodego:kimi-k2.6" -> provider=opencodego, model=kimi-k2.6
Phase 7: ("opencodego", "kimi-k2.6")
```

### Example 2: `claude --model top:opus`

```
Phase 1: "top" IS a profile -> profile=top, model="opus"
Phase 2: skipped (profile already set from Phase 1)
Phase 3: "opus" matches top.aliases["opus"] = "opencodego:kimi-k2.6"
Phase 4-5: skipped (profile alias resolved)
Phase 6: "opencodego:kimi-k2.6" -> provider=opencodego, model=kimi-k2.6
Phase 7: ("opencodego", "kimi-k2.6")
```

Same result as Example 1 -- explicit profile prefix is redundant when the
default target is already that profile.

### Example 3: `claude --model openai:gpt-4o`

```
Phase 1: "openai" is NOT a profile -> profile=None, model unchanged
Phase 2: model has ":" -> skip
Phase 3: profile is None -> skip
Phase 4: model does not start with "!" -> skip
Phase 5: AliasManager
  - ChainedAliasResolver: "openai:gpt-4o" -> "openai" aliases checked, "gpt-4o" not an alias -> no chain
  - SubstringMatcher: searches openai's aliases for substring of "gpt-4o" -> no match
  - No alias found
Phase 6: "openai:gpt-4o" -> provider=openai, model=gpt-4o
Phase 7: ("openai", "gpt-4o")
```

No alias matched -- the model name is used directly.

### Example 4: `claude --model haiku`

**Configuration:** `VDM_DEFAULT_TARGET=top` (default)

```
Phase 1: "haiku" has no ":" -> skip
Phase 2: default target "top" IS a profile -> profile = top
Phase 3: "haiku" matches top.aliases["haiku"] = "zai:haiku"
Phase 4-5: skipped (profile alias resolved)
Phase 6: "zai:haiku" -> provider=zai, model=haiku
Phase 7: ("zai", "haiku")
```

Note: `zai`'s own alias for `haiku` is `GLM-4.7-Flash`, but that alias is NOT
followed here because Phase 3 (profile alias) produces a result that goes
directly to Phase 6. The profile alias `"zai:haiku"` contains a `:`, so Phase 6
parses it as provider=zai, model=haiku. The provider's own alias for `haiku` is
only relevant if the AliasManager's `ChainedAliasResolver` processes it.

**What actually happens at the provider level:** The provider receives the model
name `haiku` and routes it to `GLM-4.7-Flash` internally (via the ZAI provider's
own model resolution, not the proxy's alias system).

### Example 5: `claude --model !my-exact-model`

```
Phase 1: "!my-exact-model" has no ":" -> skip
Phase 2: model starts with "!" -> skip
Phase 3: profile=None -> skip
Phase 4: model starts with "!" -> literal bypass
  - Strip "!" -> "my-exact-model"
  - No ":" in literal -> normalize with default target
  - LiteralPrefixResolver returns "zai:my-exact-model" (or whatever the default provider is)
Phase 5: skipped (LiteralPrefixResolver already handled it)
Phase 6: "zai:my-exact-model" -> provider=zai, model=my-exact-model
Phase 7: ("zai", "my-exact-model")
```

### Example 6: `claude --model fast-chat` where alias "fast" exists

Assume `VDM_DEFAULT_TARGET=poe` (a provider with a `fast` alias):

```
Phase 1: "fast-chat" has no ":" -> skip
Phase 2: default target "poe" is NOT a profile -> skip
Phase 3: profile=None -> skip
Phase 4: model does not start with "!" -> skip
Phase 5: AliasManager
  - SubstringMatcher: searches poe's aliases (scoped to default provider)
    - "fast" IS a substring of "fast-chat" -> match found
  - MatchRanker: only one match -> selects "fast"
    - Result: "poe:grok-4.1-fast-non-reasoning" (from poe.aliases.fast)
Phase 6: "poe:grok-4.1-fast-non-reasoning" -> provider=poe, model=grok-4.1-fast-non-reasoning
Phase 7: ("poe", "grok-4.1-fast-non-reasoning")
```

If you wanted to use the literal model name `fast-chat`, use `!fast-chat` instead.

### Example 7: `claude --model opus` with `VDM_DEFAULT_TARGET=openai`

```
Phase 1: "opus" has no ":" -> skip
Phase 2: default target "openai" is NOT a profile -> skip
Phase 3: profile=None -> skip
Phase 4: model does not start with "!" -> skip
Phase 5: AliasManager
  - SubstringMatcher: searches openai's aliases only (default target scope)
    - "opus" is an exact match in openai.aliases -> match
  - MatchRanker: selects openai:opus -> "openai:gpt-5.2"
Phase 6: "openai:gpt-5.2" -> provider=openai, model=gpt-5.2
Phase 7: ("openai", "gpt-5.2")
```

Compare with Example 1 (same input, different default target): changing the
default target from a profile to a provider completely changes the resolution
path and result.

### Example 8: `claude --model webdev-good:unknown`

Assume `webdev-good` is NOT a profile and NOT a provider:

```
Phase 1: "webdev-good" is NOT a profile -> profile=None, model unchanged
Phase 2: model has ":" -> skip
Phase 3: profile=None -> skip
Phase 4: model does not start with "!" -> skip
Phase 5: AliasManager
  - SubstringMatcher: searches "webdev-good"'s aliases only
    - "webdev-good" is not a known provider -> no aliases -> no match
  - No alias found
Phase 6: "webdev-good:unknown" -> provider=webdev-good, model=unknown
Phase 7: ("webdev-good", "unknown")
```

This will likely fail at the API call stage because `webdev-good` is not a
configured provider. The proxy resolves the model name but cannot route to an
unknown provider.

### Example 9: `claude --model poe:haiku`

```
Phase 1: "poe" is NOT a profile -> profile=None, model unchanged
Phase 2: model has ":" -> skip
Phase 3: profile=None -> skip
Phase 4: model does not start with "!" -> skip
Phase 5: AliasManager
  - SubstringMatcher: searches poe's aliases only (scoped by "poe:" prefix)
    - "haiku" is an exact match in poe.aliases -> match
  - MatchRanker: selects poe:haiku -> "poe:gpt-5.1-mini"
Phase 6: "poe:gpt-5.1-mini" -> provider=poe, model=gpt-5.1-mini
Phase 7: ("poe", "gpt-5.1-mini")
```

The `poe:` prefix scopes the search to Poe's aliases only. Even though other
providers also have a `haiku` alias, they are not considered.

---

## Configuration Quick Reference

| What | Where | Example |
|------|-------|---------|
| Provider alias (env) | `{PROVIDER}_ALIAS_{NAME}` env var | `POE_ALIAS_HAIKU=gpt-5.1-mini` |
| Profile definition | `vandamme-config.toml [profiles.name]` | `[profiles.top]` with `[profiles.top.aliases]` |
| Default target | `VDM_DEFAULT_TARGET` env var | `VDM_DEFAULT_TARGET=top` |
| Fallback aliases | `defaults.toml [defaults.aliases]` | `haiku = "zai:haiku"` |
| TOML provider aliases | `vandamme-config.toml [provider.aliases]` | `[poe.aliases] haiku = "gpt-5.1-mini"` |
| TOML config hierarchy | project > user > package | `./vandamme-config.toml` > `~/.config/vandamme-proxy/vandamme-config.toml` > `defaults.toml` |

**Alias precedence (highest to lowest):**
1. `{PROVIDER}_ALIAS_{NAME}` environment variable
2. `[provider.aliases]` in project TOML (`./vandamme-config.toml`)
3. `[provider.aliases]` in user TOML (`~/.config/vandamme-proxy/vandamme-config.toml`)
4. `[provider.aliases]` in package defaults (`defaults.toml`)
5. `[defaults.aliases]` in package defaults (global fallback)

---

## Troubleshooting

### "My alias isn't matching"

- Check **case-insensitivity**: aliases are stored lowercase, matching is
  case-insensitive. `HAIKU`, `Haiku`, and `haiku` all match.
- Check **substring matching**: alias `fast` matches input `fast-chat`, but alias
  `fast-chat` does NOT match input `fast`.
- Check **provider scope**: if your input has `provider:model`, only that
  provider's aliases are searched. Try without the prefix to use default target
  scope, or add the alias to the correct provider.
- Check **profile shadowing**: if a profile is active (default target is a
  profile), profile aliases are checked FIRST with exact matching. If the
  profile has an alias for your model name, the AliasManager never sees it.

### "Wrong provider selected"

- Check `VDM_DEFAULT_TARGET`: if it is a provider name, bare model names are
  scoped to that provider's aliases only.
- Check provider prefix: `poe:haiku` searches Poe's aliases, not all providers.
- Check MatchRanker priority: when multiple providers have the same alias, the
  default-target provider wins (priority 3 in the sort key).

### "Profile aliases ignored"

- Profile aliases only apply when a profile is **active**. A profile becomes
  active in two ways:
  1. Explicit prefix: `top:haiku` -> Phase 1 activates the `top` profile.
  2. Default target: `VDM_DEFAULT_TARGET=top` -> Phase 2 activates `top` for
     bare model names.
- Profile aliases use **exact matching** only. `opus-v2` will NOT match a
  profile alias `opus`.
- If a profile alias is not found, the model falls through to the AliasManager
  (Phase 5), which uses substring matching across the default target's aliases.

### "`!` prefix not working as expected"

- `top:!my-model` works correctly: profile prefix + literal bypass.
- `!top:opus` is **misinterpreted**: Phase 1 sees `!top` as the prefix (not a
  profile), Phase 4 treats `top` as the provider. Avoid this syntax.
- The `!` prefix only bypasses **substring matching**. Provider prefix
  normalization still applies.

### "Substring matching direction confusion"

Remember: the **alias** is checked as a substring of the **input model**, not
the other way around.

| Alias | Input | Match? |
|-------|-------|--------|
| `fast` | `fast-chat` | Yes (alias is substring of input) |
| `fast-chat` | `fast` | **No** (alias is NOT substring of input) |

### Debug mode

Set `LOG_LEVEL=DEBUG` to see each resolution phase in the logs. This is the
single most useful debugging tool for understanding why a model resolved the
way it did. See [Phase 7: Final Result](#phase-7-final-result) for example log
output.

---

## Appendix A: AliasManager Architecture (for developers)

This appendix describes the internal architecture of the alias resolution system
for developers who need to modify or extend it.

### Data classes

#### `ResolutionContext`

```python
# src/core/alias/resolver.py:18-33
@dataclass(frozen=True)
class ResolutionContext:
    model: str           # The original model name to resolve
    provider: str | None # Optional provider scope for resolution
    default_target: str  # Default provider from configuration
    aliases: dict[str, dict[str, str]]  # {provider: {alias: target}}
    metadata: dict[str, Any]  # Inter-resolver communication channel
```

The context is **immutable** (frozen dataclass). Resolvers that need to pass
data to subsequent resolvers use `with_updates()` to create a new context with
modified `metadata`. Currently, `SubstringMatcher` stores its matches in
`metadata["substring_matches"]` for `MatchRanker` to consume.

#### `ResolutionResult`

```python
# src/core/alias/resolver.py:53-69
@dataclass(frozen=True)
class ResolutionResult:
    resolved_model: str      # The resolved model name
    provider: str | None     # The provider to use
    was_resolved: bool       # True if an alias was found
    resolution_path: tuple   # Intermediate aliases for chain tracing
    matches: tuple           # Candidate matches for MatchRanker
```

The `was_resolved` flag distinguishes three cases:
- `True`: an alias was found and resolved.
- `False` + `matches` non-empty: `SubstringMatcher` found candidates; the chain
  continues to `MatchRanker`.
- `False` + `resolved_model != model`: `LiteralPrefixResolver` handled the
  bypass (special case in the chain).

### The four resolver components

| # | Class | Priority | Role |
|---|-------|----------|------|
| 1 | `LiteralPrefixResolver` | 10 | Handles `!` prefix. Strips `!`, adds provider prefix. Returns `was_resolved=False` to signal "bypass, not alias resolution." |
| 2 | `ChainedAliasResolver` | 20 | Follows alias chains (e.g., `zai:haiku` -> `GLM-4.7-Flash`). Only activates when model contains `:`. Max 10 iterations with cycle detection. |
| 3 | `SubstringMatcher` | 30 | Finds all aliases that are substrings of the input model. Creates underscore/hyphen variations. Scopes to a single provider. Stores matches in context metadata. |
| 4 | `MatchRanker` | 40 | Reads matches from context metadata, sorts by the 5-tuple key, selects the best match. Handles cross-provider alias targets. |

### Chain orchestration (`AliasResolverChain`)

The chain executes resolvers in priority order (lower = earlier). It has special
handling for inter-resolver communication:

1. **SubstringMatcher -> MatchRanker**: When `SubstringMatcher` returns a result
   with `matches` but `was_resolved=False`, the chain stores the matches in
   context metadata and continues to the next resolver (`MatchRanker`).

2. **MatchRanker -> ChainedAliasResolver**: After `MatchRanker` selects a match,
   the chain checks if the resolved model might itself be an alias (contains `:`
   or is in the provider's alias map). If so, it re-runs `ChainedAliasResolver`
   on the resolved model and merges the resolution paths.

3. **First-wins**: The first resolver to return a "terminal" result (either
   `was_resolved=True` or a modified `resolved_model` from `LiteralPrefixResolver`)
   ends the chain.

### `AliasResolverCache`

```python
# src/core/alias_manager.py:58-164
@dataclass
class AliasResolverCache:
    ttl_seconds: float = 300.0   # 5 minutes default
    max_size: int = 1000         # Max cached entries
```

Cache entries are invalidated by two mechanisms:
- **TTL expiry**: entries older than 5 minutes are evicted on access.
- **Generation counter**: when `invalidate()` is called (e.g., after alias
  reload), the generation increments and all existing entries are silently
  discarded on their next access.

Cache keys are `"provider:model"` when a provider scope is given, or just
`"model"` otherwise. Literal-prefixed models (`!model`) bypass the cache
entirely.

### MatchRanker sort key (the exact 5-tuple)

```python
key=lambda m: (
    0 if m.is_exact else 1,                          # 1. Exact match (0) before substring (1)
    -m.length,                                        # 2. Longer alias first (negated for descending)
    0 if m.provider == context.default_target else 1, # 3. Default provider (0) before others (1)
    m.provider,                                       # 4. Provider name ascending
    m.alias,                                          # 5. Alias name ascending
)
```

This tuple is compared lexicographically by Python's sort, so priority 1 is the
most significant and priority 5 is the least significant tiebreaker.
