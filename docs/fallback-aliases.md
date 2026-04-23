# Fallback Model Aliases: Smart Defaults for Seamless Usage

## Overview

When using Claude Code with Vandamme Proxy, you often work with standard model names like `haiku`, `sonnet`, and `opus`. But what happens when your configured provider doesn't have models with those exact names? Previously, you'd need to manually configure aliases for every provider. Now, Vandamme Proxy automatically provides sensible fallback defaults.

> **See also:** [Model Name Resolution Guide](model-resolution.md) — how fallback aliases fit into the full resolution pipeline.

## The Problem: One Size Doesn't Fit All

Different LLM providers have different model naming conventions:

| Provider | Available Models | Claude Code Names |
|----------|------------------|------------------|
| OpenAI | `gpt-5.1-mini`, `gpt-5.1-codex`, `gpt-5.2` | haiku, sonnet, opus |
| Poe | `gpt-5.1-mini`, `gpt-5.1-codex-mini`, `gpt-5.1-codex-max` | haiku, sonnet, opus |
| Anthropic | `claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022` | haiku, sonnet, opus |

Without aliases, requests like "claude --model haiku" would fail with "model not found" errors.

## The Solution: Intelligent Fallbacks

Vandamme Proxy now automatically maps standard Claude model names to appropriate models for each provider. These fallbacks are:

- **Applied automatically**: No configuration needed
- **Provider-specific**: Each provider gets appropriate defaults
- **Overrideable**: Your custom aliases take precedence
- **Hierarchical**: Local > User > Package defaults

### Default Fallback Mappings

Each provider defines its own aliases in `src/config/defaults.toml`:

| Alias | Poe Provider | OpenAI Provider | Anthropic Provider |
|-------|-------------|-----------------|-------------------|
| `haiku` | `gpt-5.1-mini` | `gpt-5.1-mini` | `claude-3-5-haiku-20241022` |
| `sonnet` | `gpt-5.1-codex-mini` | `gpt-5.1-codex` | `claude-3-5-sonnet-20241022` |
| `opus` | `gpt-5.1-codex-max` | `gpt-5.2` | `claude-3-opus-20240229` |

Additionally, `[defaults.aliases]` provides global fallback aliases that apply to **all** providers when no provider-specific alias exists. These typically use chained aliases (e.g. `haiku = "zai:haiku"`) so that updating one provider's aliases automatically propagates everywhere.

## How It Works

### 1. Automatic Detection

When Vandamme Proxy starts, it:

1. Loads provider configurations
2. Checks for explicit aliases (environment variables)
3. Applies fallback defaults for missing aliases
4. Logs which aliases are active

### 2. Configuration Hierarchy

Fallbacks follow a clear priority order:

```bash
# Highest Priority (overrides everything)
./vandamme-config.toml
├── [poe.aliases]
│   └── haiku = "my-preferred-model"

# Medium Priority (your personal settings)
~/.config/vandamme-proxy/vandamme-config.toml
├── [poe.aliases]
│   └── sonnet = "my-sonnet-model"

# Lowest Priority (built-in defaults)
src/config/defaults.toml
└── [poe.aliases]
    ├── haiku = "gpt-5.1-mini"
    ├── sonnet = "gpt-5.1-codex-mini"
    └── opus = "gpt-5.1-codex-max"
```

### 3. Smart Resolution

When you request a model:

```python
# 1. Check for exact alias match
"haiku" → matches POE_ALIAS_HAIKU or fallback

# 2. Apply provider prefix
"poe:haiku" → uses poe provider's haiku alias

# 3. Resolve to actual model
"haiku" → "poe:gpt-5.1-mini"
```

## Usage Examples

### Out of the Box

No configuration needed - fallbacks work immediately:

```bash
# Set up any provider
export POE_API_KEY=your-poe-key

# Use Claude Code with standard model names
claude --model haiku "Quick response"      # Uses gpt-5.1-mini
claude --model sonnet "Balanced task"     # Uses gpt-5.1-codex-mini
claude --model opus "Complex reasoning"    # Uses gpt-5.1-codex-max
```

### Custom Overrides

Need different models? Just set environment variables:

```bash
# Override specific aliases
export POE_ALIAS_HAIKU="my-custom-haiku"
export POE_ALIAS_SONNET="my-preferred-sonnet"

# Keep opus fallback
claude --model haiku "Uses your custom model"
claude --model opus "Still uses gpt-5.1-codex-max fallback"
```

### Project-Specific Settings

Create `./vandamme-config.toml` in your project:

```toml
[poe]
base-url = "https://custom-poe.com"
timeout = 60
[poe.aliases]
haiku = "project-specific-haiku"
sonnet = "team-sonnet-choice"

[openai]
timeout = 120
[openai.aliases]
haiku = "gpt-5.1-mini"
sonnet = "gpt-5.1-codex"
fast = "gpt-5.1-mini"
```

### Personal Defaults

Create `~/.config/vandamme-proxy/vandamme-config.toml`:

```toml
[poe]
# My personal preferences
[poe.aliases]
haiku = "poe-grok-4o-mini"
opus = "poe-claude-sonnet-20241022"

[openai]
# When I use OpenAI directly
[openai.aliases]
haiku = "gpt-5.1-mini"
```

## Visual Feedback

When Vandamme Proxy starts, it shows active aliases:

```
✨ Model Aliases (3 configured across 1 providers):
   📦 Includes 3 fallback defaults from configuration

   poe (3 aliases, 3 fallbacks):
   Alias                Target Model                             Type
   -------------------- ---------------------------------------- ----------
   haiku                gpt-5.1-mini                             fallback
   sonnet               gpt-5.1-codex-mini                       fallback
   opus                 gpt-5.1-codex-max                        fallback

   💡 Use aliases in your requests:
      Example: model='haiku' → resolves to 'poe:gpt-5.1-mini'
                (from configuration defaults)
```

## Benefits

### For Users

- **Zero Configuration**: Works immediately with any provider
- **Consistent Experience**: Same model names work across providers
- **No Surprises**: Clear logging shows which models are used

### For Developers

- **Flexible Override**: Three levels of customization
- **Clean Implementation**: Separate from core logic
- **Easy Testing**: Configurable per project

### For Teams

- **Shared Defaults**: User-level configuration for consistency
- **Project Overrides**: Project-specific model choices
- **Documentation**: Clear visibility into active aliases

## Advanced Usage

### Adding Provider Defaults

Want to add defaults for new providers? Just update the TOML:

```toml
[newprovider.aliases]
haiku = "newprovider-haiku-v1"
sonnet = "newprovider-sonnet-v2"
opus = "newprovider-opus-v3"

[anotherprovider.aliases]
# Different defaults for different use cases
haiku = "fast-model-1"
sonnet = "balanced-model-2"
opus = "powerful-model-3"
```

### Mixed Workflows

Some projects might use different providers:

```bash
# Project A: Fast development with Poe
VDM_DEFAULT_TARGET=poe

# Project B: Production with OpenAI
VDM_DEFAULT_TARGET=openai

# Both work with same model names!
claude --model haiku  # Uses Poe's fast model
```

## Technical Details

### Implementation

The fallback system uses:

1. **tomli** for TOML parsing (Python 3.10 compatible)
2. **Path hierarchy** for configuration discovery
3. **Caching** for performance (loads once per startup)
4. **Validation** to ensure provider existence

### File Locations

- **Package defaults**: `src/config/defaults.toml`
- **User configuration**: `~/.config/vandamme-proxy/vandamme-config.toml`
- **Project overrides**: `./vandamme-config.toml`

### Integration Points

- **AliasManager**: Loads fallbacks during initialization
- **ModelManager**: Resolves aliases with fallback support
- **CLI**: Shows fallback status in alias summaries

## Troubleshooting

### Fallbacks Not Working?

1. **Check provider configuration**:
   ```bash
   export POE_API_KEY=your-key  # Provider must be configured
   ```

2. **Verify TOML syntax**:
   ```bash
   python -c "import tomli; tomli.load(open('vandamme-config.toml', 'rb'))"
   ```

3. **Check logs**:
   ```bash
   export LOG_LEVEL=DEBUG
   vdm server start
   ```

### Unexpected Model Names?

1. **Check your config files**:
   ```bash
   # See which config files exist
   ls -la ./vandamme-config.toml
   ls -la ~/.config/vandamme-proxy/vandamme-config.toml
   ```

2. **Check environment overrides**:
   ```bash
   env | grep "_ALIAS_"
   ```

3. **Use the API endpoint**:
   ```bash
   curl http://localhost:8082/v1/aliases
   ```

## Future Enhancements

The fallback system is designed for extensibility:

- **More Providers**: Easy to add defaults for new providers
- **Dynamic Updates**: Could support hot-reloading configs
- **Validation**: Could validate model names against provider APIs
- **Analytics**: Could track which fallbacks are most useful

## Conclusion

Fallback aliases make Vandamme Proxy more user-friendly while maintaining full flexibility. You get sensible defaults out of the box but retain complete control when you need it. This is especially valuable when switching between providers or when working with teams that have different model preferences.

The hierarchical configuration system ensures that defaults work for everyone while allowing customization at the right scope - personal, project, or organization level.
