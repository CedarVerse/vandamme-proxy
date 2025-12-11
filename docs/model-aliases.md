# VDM_ALIAS_* Configuration Guide

## Overview

The VDM_ALIAS_* mechanism allows you to create flexible model aliases that enable case-insensitive substring matching for model selection. This feature makes it easier to work with multiple models and providers by creating memorable names and automatic matching patterns.

## Key Features

- **Case-Insensitive Matching**: `VDM_ALIAS_FAST` matches "fast", "FAST", "FastModel", etc.
- **Substring Matching**: Any model name containing "haiku" will match `VDM_ALIAS_HAIKU`
- **Flexible Hyphen/Underscore Matching**: Aliases match model names regardless of whether they use hyphens or underscores
  - `VDM_ALIAS_MY_ALIAS` matches "my-alias", "my_alias", "oh-my-alias-model", and "oh-my_alias_model"
- **Provider Prefix Support**: Alias values can include provider prefixes (e.g., "poe:gpt-4o-mini")
- **Flexible Naming**: Support any alias name, not just tier-specific ones
- **Zero Breaking Changes**: Existing functionality is preserved when no aliases are configured

## Configuration

### Basic Alias Setup

```bash
# Simple alias without provider prefix
VDM_ALIAS_CHAT=gpt-4o

# Alias with provider prefix
VDM_ALIAS_HAIKU=poe:gpt-4o-mini
```

### Tier-Based Aliases

Create tier-based aliases for consistent model selection:

```bash
# Tier-based aliases for Claude Code model selection
VDM_ALIAS_HAIKU=poe:gpt-4o-mini
VDM_ALIAS_SONNET=openai:gpt-4o
VDM_ALIAS_OPUS=anthropic:claude-3-opus-20240229
```

### Custom Aliases

Create aliases for specific use cases:

```bash
# Use case-specific aliases
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
VDM_ALIAS_FAST=poe:gpt-4o-mini
VDM_ALIAS_SMART=openai:o1-preview
VDM_ALIAS_CODE=openai:o1-preview
VDM_ALIAS_EMBED=openai:text-embedding-ada-002
```

### Provider-Specific Aliases

Create aliases for the same use case across different providers:

```bash
# Fast models from different providers
VDM_ALIAS_OPENAI_FAST=openai:gpt-4o-mini
VDM_ALIAS_ANTHROPIC_FAST=anthropic:claude-3-5-haiku-20241022
VDM_ALIAS_POE_FAST=poe:gpt-4o-mini
```

## How It Works

### Alias Resolution Algorithm

1. **Load Aliases**: Read all `VDM_ALIAS_*` environment variables at startup
2. **Normalize**: Store alias names in lowercase for case-insensitive matching
3. **Match**: Find aliases where the alias name is a substring of the requested model
4. **Prioritize**: Select the best match based on priority rules
5. **Resolve**: Return the alias target value

### Priority Order

When multiple aliases match a model name:

1. **Exact Match First**: If an alias exactly matches the model name, it's chosen immediately
   - Underscores in aliases are converted to hyphens for exact matching
2. **Longest Substring**: Among substring matches, the longest alias name wins
3. **Alphabetical Order**: If multiple aliases have the same length, the alphabetically first wins

### Examples

```bash
# Configuration
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022
VDM_ALIAS_FAST=poe:gpt-4o-mini
VDM_ALIAS_HAIKU=poe:gpt-4o-mini
```

**Resolution Examples**:

- `"chat"` → `anthropic:claude-3-5-sonnet-20241022` (exact match)
- `"ChatModel"` → `anthropic:claude-3-5-sonnet-20241022` (case-insensitive)
- `"my-haiku-model"` → `poe:gpt-4o-mini` (substring match)
- `"Super-Fast-Response"` → `poe:gpt-4o-mini` (substring match)
- `"chathaiiku"` → `anthropic:claude-3-5-sonnet-20241022` (longest match wins)
- `"my-alias"` → `openai:gpt-4o` (from `VDM_ALIAS_MY_ALIAS`, underscore to hyphen)
- `"oh-my-alias-is-great"` → `openai:gpt-4o` (from `VDM_ALIAS_MY_ALIAS`, substring match with normalization)

## API Usage

### List All Aliases

```bash
# List all configured aliases
curl http://localhost:8082/v1/aliases
```

**Response**:
```json
{
  "object": "list",
  "data": [
    {
      "alias": "haiku",
      "target": "poe:gpt-4o-mini",
      "provider": "poe",
      "model": "gpt-4o-mini"
    },
    {
      "alias": "fast",
      "target": "openai:gpt-4o-mini",
      "provider": "openai",
      "model": "gpt-4o-mini"
    },
    {
      "alias": "chat",
      "target": "anthropic:claude-3-5-sonnet-20241022",
      "provider": "anthropic",
      "model": "claude-3-5-sonnet-20241022"
    }
  ]
}
```

### Using Aliases in Requests

```bash
# Direct alias match
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "haiku",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Substring match
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "my-custom-haiku-model",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Claude Code Integration

Use aliases with Claude Code CLI:

```bash
# Set up proxy
export ANTHROPIC_BASE_URL=http://localhost:8082

# Use alias directly
claude --model haiku "Quick response needed"

# Use substring matching
claude --model any-Haiku-model-will-do "Process this quickly"
```

## Environment Variable Rules

### Naming Convention

- **Prefix**: All aliases must start with `VDM_ALIAS_`
- **Case**: Variable names are case-sensitive but aliases are stored in lowercase
- **Characters**: Use letters, numbers, and underscores in alias names
- **Conversion**: Underscores in variable names become part of the alias name but also match hyphens

### Value Format

```bash
# Plain model name (uses default provider)
VDM_ALIAS_FAST=gpt-4o-mini

# With provider prefix
VDM_ALIAS_FAST=openai:gpt-4o-mini

# With special characters in model names
VDM_ALIAS_CUSTOM=custom-provider/model-v1.2.3
```

### Validation Rules

1. **No Empty Values**: Empty or whitespace-only values are skipped
2. **No Circular References**: An alias cannot reference itself
3. **Format Validation**: Values must match valid model name patterns
4. **Automatic Logging**: Invalid configurations are logged with warnings

## Best Practices

### Naming Conventions

```bash
# Use descriptive, memorable names
VDM_ALIAS_FAST=gpt-4o-mini
VDM_ALIAS_SMART=o1-preview
VDM_ALIAS_CHAT=claude-3-5-sonnet-20241022

# Use consistent patterns
VDM_ALIAS_OPENAI_FAST=openai:gpt-4o-mini
VDM_ANTHROPIC_FAST=anthropic:claude-3-5-haiku-20241022
```

### Organize by Use Case

```bash
# Development aliases
VDM_ALIAS_DEV_FAST=gpt-4o-mini
VDM_ALIAS_DEV_SMART=o1-preview

# Production aliases
VDM_ALIAS_PROD_CHAT=claude-3-5-sonnet-20241022
VDM_ALIAS_PROD_ANALYTICS=o1-preview

# Testing aliases
VDM_ALIAS_TEST_MOCK=gpt-4o-mini
```

### Documentation

Document your aliases for team members:

```bash
# Team-specific aliases - see docs/model-aliases.md
# To use these aliases in Claude Code,
# run `/model team-chat` or `/model team-code`
VDM_ALIAS_TEAM_CHAT=anthropic:claude-3-5-sonnet-20241022
VDM_ALIAS_TEAM_CODE=openai:o1-preview
```

## Troubleshooting

### Common Issues

#### Alias Not Matching

```bash
# Check if alias is loaded
curl http://localhost:8082/v1/aliases

# Verify model name contains the alias substring
# Example: "haiku" matches "my-haiku-model" but not "haikumodel"
```

#### Provider Not Found

```bash
# Error: Provider 'unknown' not found
VDM_ALIAS_FAST=unknown:gpt-4o  # Invalid provider

# Fix: Use a configured provider
VDM_ALIAS_FAST=openai:gpt-4o
```

#### Circular Reference

```bash
# Error: Circular alias reference detected
VDM_ALIAS_WRONG=wrong  # Invalid
```

### Debug Logging

Enable debug logging to see alias resolution:

```bash
export LOG_LEVEL=DEBUG
vdm server start
```

**Sample Debug Output**:
```
DEBUG: Resolved model alias 'my-haiku-model' -> 'poe:gpt-4o-mini' (matched alias 'haiku')
```

### Validation Commands

```bash
# Check loaded aliases
curl http://localhost:8082/v1/aliases

# Test alias resolution
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"model": "test-alias-name", "max_tokens": 1, "messages": [{"role": "user", "content": "test"}]}'
```

## Migration Guide

### From Direct Model Names

If you're currently using direct model names:

**Before**:
```bash
claude --model claude-3-5-haiku-20241022
```

**After**:
```bash
# Configure alias
VDM_ALIAS_HAIKU=poe:gpt-4o-mini

# Use alias
claude --model haiku
```

### From Multiple Providers

If you're switching between providers:

**Before**:
```bash
# Use provider prefix directly
claude --model poe:gpt-4o-mini
claude --model anthropic:claude-3-5-sonnet-20241022
```

**After**:
```bash
# Configure aliases
VDM_ALIAS_FAST=poe:gpt-4o-mini
VDM_ALIAS_CHAT=anthropic:claude-3-5-sonnet-20241022

# Use aliases
claude --model fast
claude --model chat
```

## Security Considerations

### Access Control

- **Admin Only**: Only administrators can configure aliases via environment variables
- **Runtime Protection**: Aliases cannot be modified at runtime
- **No User Input**: Alias values are not influenced by user requests

### Provider Authentication

- **Existing Security**: Provider API keys are still required and validated
- **No Bypass**: Aliases don't bypass any authentication mechanisms
- **Header Preservation**: Custom headers are still applied to resolved models

## Performance

### Impact

- **Minimal Overhead**: Alias resolution is O(n) where n is the number of aliases
- **Cached at Startup**: Aliases are loaded once and cached in memory
- **No Network Calls**: Resolution happens entirely in-memory
- **Typical Usage**: With < 100 aliases, the performance impact is negligible

### Optimization

- **Order Matters**: Place more specific aliases before general ones
- **Avoid Overlaps**: Minimize overlapping alias names for predictable behavior
- **Regular Cleanup**: Remove unused aliases to maintain clarity

## Reference

### API Endpoints

#### GET /v1/aliases

List all configured model aliases.

**Response Format**:
```json
{
  "object": "list",
  "data": [
    {
      "alias": "string",
      "target": "string",
      "provider": "string",
      "model": "string"
    }
  ]
}
```

### Environment Variables

| Variable | Format | Example | Description |
|----------|--------|---------|-------------|
| `VDM_ALIAS_<NAME>` | `<TARGET>` | `VDM_ALIAS_FAST=openai:gpt-4o-mini` | Create a model alias |

### Error Codes

| Error | Description | Solution |
|-------|-------------|----------|
| 401 | Invalid API key | Check `ANTHROPIC_API_KEY` configuration |
| 404 | Provider not found | Configure the provider with `{PROVIDER}_API_KEY` |
| 500 | Internal server error | Check server logs for alias resolution errors |

### Supported Characters

**Alias Names**:
- Letters: a-z, A-Z
- Numbers: 0-9
- Underscore: _

**Target Values**:
- Letters, numbers, hyphens, slashes, dots, colons
- Provider prefix format: `provider:model`
- Plain model format: `model-name`
