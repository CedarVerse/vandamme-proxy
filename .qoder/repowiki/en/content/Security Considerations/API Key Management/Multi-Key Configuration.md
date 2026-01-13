# Multi-Key Configuration

<cite>
**Referenced Files in This Document**   
- [multi-api-keys.md](file://docs/multi-api-keys.md)
- [provider_config.py](file://src/core/provider_config.py)
- [provider_manager.py](file://src/core/provider_manager.py)
- [key_rotation.py](file://src/api/services/key_rotation.py)
- [multi-provider.env](file://examples/multi-provider.env)
</cite>

## Table of Contents
1. [Overview](#overview)
2. [Configuration Methods](#configuration-methods)
3. [Key Selection and Rotation](#key-selection-and-rotation)
4. [Failover Behavior](#failover-behavior)
5. [Practical Examples](#practical-examples)
6. [Configuration Pitfalls](#configuration-pitfalls)
7. [Performance Considerations](#performance-considerations)
8. [Integration with Key Rotation System](#integration-with-key-rotation-system)
9. [Troubleshooting](#troubleshooting)

## Overview

The multi-key configuration system in vandamme-proxy enables enhanced reliability and scalability by allowing multiple API keys per provider. This feature provides load distribution across keys, automatic failover during authentication failures, rate limit management, and high availability even when individual keys fail. The system supports both environment variable and TOML configuration methods, with consistent parsing behavior across both formats.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L3-L13)

## Configuration Methods

### Environment Variables

Multiple API keys can be configured through environment variables using whitespace separation. The system parses the API key string by splitting on whitespace characters:

```bash
# Single API key (traditional format)
OPENAI_API_KEY="sk-your-single-key"

# Multiple API keys for load balancing and failover
OPENAI_API_KEY="sk-key1 sk-key2 sk-key3"

# Multiple keys for different providers
ANTHROPIC_API_KEY="sk-ant-key1 sk-ant-key2 sk-ant-backup"
POE_API_KEY="poe-key-1 poe-key-2"
AZURE_API_KEY="azure-key-1 azure-key-2"
```

The first key in the list becomes the initial key for the provider, while all keys are available for rotation. Empty values or trailing spaces are not allowed and will trigger configuration validation errors.

### TOML Configuration

The system also supports multi-key configuration through TOML files. When using TOML configuration, the `api-key` field can contain multiple keys separated by whitespace, with the same parsing rules as environment variables:

```toml
[openai]
api-key = "sk-key1 sk-key2 sk-key3"
base-url = "https://api.openai.com/v1"

[anthropic]
api-key = "sk-ant-key1 sk-ant-key2"
base-url = "https://api.anthropic.com"
```

Configuration precedence follows the order: environment variables override TOML configuration, which in turn overrides default values. This allows for flexible configuration management across different deployment environments.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L18-L31)
- [provider_manager.py](file://src/core/provider_manager.py#L257-L267)
- [provider_config.py](file://src/core/provider_config.py#L83-L97)

## Key Selection and Rotation

### Round-Robin Rotation

The system implements a round-robin rotation strategy for distributing requests across multiple API keys. Key selection follows these principles:

1. **Process-Global State**: Rotation state is shared across all requests within the process
2. **Thread-Safe**: Uses asyncio locks to ensure concurrent request safety
3. **Per-Provider Tracking**: Each provider maintains independent rotation state
4. **Ordered Rotation**: Keys are selected in the order they appear in the configuration

The rotation state is stored in the provider manager using a dictionary that maps provider names to their current key index. This ensures consistent rotation behavior across concurrent requests.

### Rotation Implementation

The key rotation mechanism is implemented through the `make_next_provider_key_fn` function, which creates a reusable key rotator for each provider:

```python
def make_next_provider_key_fn(*, provider_name: str, api_keys: list[str]) -> NextApiKey:
    """Create a reusable provider API key rotator."""
    
    async def _next_provider_key(exclude: set[str]) -> str:
        if len(exclude) >= len(api_keys):
            raise HTTPException(status_code=429, detail="All provider API keys exhausted")
            
        while True:
            k = await config.provider_manager.get_next_provider_api_key(provider_name)
            if k not in exclude:
                return k
                
    return _next_provider_key
```

This implementation ensures that excluded keys (those that have failed) are skipped during rotation, and a new key is selected from the available pool.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L35-L38)
- [key_rotation.py](file://src/api/services/key_rotation.py#L14-L32)
- [provider_manager.py](file://src/core/provider_manager.py#L43-L45)

## Failover Behavior

### Automatic Failover Triggers

The system automatically rotates to the next available key when encountering specific failure conditions:

- HTTP 401 (Unauthorized)
- HTTP 403 (Forbidden)
- HTTP 429 (Rate Limited)
- Error messages containing "insufficient_quota"

When any of these conditions occur, the current key is temporarily excluded from rotation, and the system attempts to use the next available key from the pool. The proxy continues attempting all configured keys before returning an error to the client.

### Exhaustion Handling

When all keys in a provider's pool have been exhausted (either through failure or rate limiting), the system returns an HTTP 429 error with the message "All provider API keys exhausted". This occurs when the number of excluded keys equals or exceeds the total number of configured keys for a provider.

The failover mechanism is implemented in the key rotation function, which checks the exclude set size against the total number of available keys:

```python
if len(exclude) >= len(api_keys):
    raise HTTPException(status_code=429, detail="All provider API keys exhausted")
```

This ensures that clients receive a clear error message when no viable keys are available.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L42-L49)
- [key_rotation.py](file://src/api/services/key_rotation.py#L24-L25)
- [test_api_key_rotation.py](file://tests/unit/test_api_key_rotation.py#L119-L137)

## Practical Examples

### Multi-Provider Environment Configuration

The `multi-provider.env` example demonstrates a real-world multi-key setup for various providers:

```bash
# OpenAI Provider with multiple keys
OPENAI_API_KEY=sk-openai-key1 sk-openai-key2 sk-openai-backup
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic Direct Provider with multiple keys
ANTHROPIC_API_KEY=sk-ant-key1 sk-ant-key2 sk-ant-backup
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_FORMAT=anthropic

# AWS Bedrock Provider
BEDROCK_API_KEY=aws-key1 aws-key2
BEDROCK_BASE_URL=https://bedrock-runtime.us-west-2.amazonaws.com
BEDROCK_API_FORMAT=anthropic

# Azure OpenAI Provider
AZURE_API_KEY=azure-key1 azure-key2
AZURE_BASE_URL=https://your-resource.openai.azure.com
AZURE_API_VERSION=2024-02-15-preview

# Set default provider
VDM_DEFAULT_PROVIDER=openai
```

This configuration enables high availability across multiple providers, with each provider having a pool of keys for load balancing and failover.

### Production Deployment Example

A production-ready configuration might include:

```bash
# Multiple static keys for resilience
OPENAI_API_KEY="sk-prod1 sk-prod2 sk-backup"
ANTHROPIC_API_KEY="sk-ant1 sk-ant2"

# Passthrough for client autonomy
POE_API_KEY=!PASSTHRU

# Configure provider-specific settings
OPENAI_BASE_URL="https://api.openai.com/v1"
ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Set default provider
VDM_DEFAULT_PROVIDER="openai"
```

This pattern combines multiple static keys for critical providers with passthrough mode for client-managed providers, providing both reliability and flexibility.

**Section sources**
- [multi-provider.env](file://examples/multi-provider.env)
- [multi-api-keys.md](file://docs/multi-api-keys.md#L55-L66)

## Configuration Pitfalls

### Mixed Configuration Error

The system does not allow mixing the `!PASSTHRU` sentinel with static API keys for the same provider. This configuration will raise a validation error:

```bash
# INVALID: Mixed static and passthrough (will raise an error)
ANTHROPIC_API_KEY="!PASSTHRU sk-ant-key"
```

The error message will be: "Configuration Error: Cannot mix !PASSTHRU with static keys". This restriction exists because the system cannot determine whether to use the client-provided key or rotate through static keys.

### Empty Key Detection

The configuration validation checks for empty API key values and will reject configurations that contain them:

```bash
# INVALID: Contains empty key (will raise an error)
OPENAI_API_KEY="sk-key1  sk-key3"  # Note the double space
```

The error message will be: "Configuration Error: Empty API key detected". This prevents configuration issues caused by accidental whitespace or malformed key lists.

### Delimiter Usage

The system uses whitespace (spaces, tabs, newlines) as delimiters for separating multiple API keys. Commas, semicolons, or other characters are not supported as delimiters. Using incorrect delimiters will result in the entire string being treated as a single API key, which will likely fail authentication.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L95-L97)
- [provider_config.py](file://src/core/provider_config.py#L90-L94)
- [provider_manager.py](file://src/core/provider_manager.py#L262-L266)

## Performance Considerations

### Key Pool Sizing

Optimal key pool sizing depends on several factors:

1. **Request Volume**: Higher request volumes benefit from larger key pools to distribute load
2. **Rate Limits**: Key pools should be sized to stay within individual key rate limits
3. **Failure Tolerance**: Larger pools provide greater resilience to individual key failures
4. **Provider Limits**: Some providers may have limits on the number of active keys

A general guideline is to maintain at least 3-5 keys per provider for production systems, with additional keys for backup and failover scenarios.

### Geographic Distribution

For providers that support regional endpoints, consider geographic distribution strategies:

1. **Latency Optimization**: Distribute keys across regions closest to your users
2. **Compliance Requirements**: Ensure keys are in regions that meet data residency requirements
3. **Fault Isolation**: Use keys from different availability zones for enhanced reliability

When using geographically distributed keys, monitor performance metrics to ensure the rotation strategy is effectively balancing load across regions.

### Monitoring and Metrics

Enable request metrics to monitor key rotation and performance:

```bash
LOG_LEVEL=DEBUG
```

The logs will show:
- API key hashes (first 8 characters)
- Which key was used for each request
- When rotation occurs
- Authentication failure details

This information is crucial for optimizing key pool sizing and identifying performance bottlenecks.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L106-L113)
- [key_rotation.py](file://src/api/services/key_rotation.py#L24-L25)

## Integration with Key Rotation System

### Interaction with Passthrough Mode

The multi-key configuration system interacts with the key rotation system in specific ways:

1. **Static Keys**: When multiple static keys are configured, the rotation system manages key selection and failover
2. **Passthrough Mode**: When `!PASSTHRU` is configured, the rotation system is disabled for that provider, and the client-provided key is used directly
3. **No Mixed Mode**: The system prevents mixing static keys with passthrough mode for the same provider

The `uses_passthrough` property in the `ProviderConfig` class determines whether a provider uses client-provided keys or static key rotation:

```python
@property
def uses_passthrough(self) -> bool:
    """Check if this provider uses client API key passthrough"""
    if self.api_keys is not None:
        return False
    return self.api_key == PASSTHROUGH_SENTINEL
```

### Quota Sharing

The system does not implement quota sharing between keys. Each key maintains its own rate limits and quotas as defined by the provider. The rotation system's role is to distribute requests across keys to avoid hitting individual key limits, but it does not aggregate or balance quotas across keys.

This approach provides predictable behavior and avoids complexity in quota management, but requires careful planning to ensure sufficient total quota across all keys in the pool.

**Section sources**
- [provider_config.py](file://src/core/provider_config.py#L33-L39)
- [key_rotation.py](file://src/api/services/key_rotation.py#L56-L57)

## Troubleshooting

### Common Issues

#### All Keys Exhausted
```
HTTP 429: All provider API keys exhausted
```
**Solution**: Check if all keys are valid or temporarily rate-limited. Verify that the keys have sufficient quota and are not revoked.

#### Mixed Configuration Error
```
Configuration Error: Cannot mix !PASSTHRU with static keys
```
**Solution**: Use either all static keys or `!PASSTHRU`, not both. Choose the appropriate mode based on your security and operational requirements.

#### Empty Key Detection
```
Configuration Error: Empty API key detected
```
**Solution**: Ensure no empty strings in your key list. Check for accidental double spaces or trailing spaces in your configuration.

### Debugging Steps

1. **Check Configuration**:
   ```bash
   env | grep API_KEY
   ```

2. **Verify Key Format**:
   - Ensure proper whitespace separation
   - Check for trailing spaces
   - Validate key formats

3. **Monitor Logs**:
   ```bash
   vdm server start 2>&1 | grep -E "(API KEY|rotation|exhausted)"
   ```

4. **Test Individual Keys**:
   Temporarily use single keys to isolate issues and verify each key's validity independently.

**Section sources**
- [multi-api-keys.md](file://docs/multi-api-keys.md#L157-L190)
- [api-key-passthrough.md](file://docs/api-key-passthrough.md#L160-L164)