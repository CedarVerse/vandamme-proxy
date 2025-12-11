# API Key Passthrough Feature

The Vandamme Proxy supports API key passthrough, allowing providers to use the client's API key instead of a statically configured one.

## Configuration

To enable API key passthrough for a provider, set the provider's API key environment variable to `!PASSTHRU`.

Syntax for the env var: `<provider>_API_KEY='!PASSTHRU'`

See examples below.

## Key Design Principles

### Explicit Configuration for Security
Using an explicit sentinel value (`!PASSTHRU`) provides security advantages:

- **No accidental passthrough**: API keys must be explicitly marked for passthrough
- **Clear intent**: Configuration clearly shows which providers use client keys
- **Reduced risk**: Lower chances of accidentally sending secrets to wrong endpoints
- **Auditability**: Easy to identify passthrough providers in configuration files

### Mixed Mode Support for Maximum Flexibility
The proxy simultaneously supports both static and passthrough providers, enabling:

- **Cost control**: Use your own keys for expensive providers
- **Client autonomy**: Allow clients to use their own keys for specific providers
- **Gradual migration**: Move providers to passthrough one at a time
- **Hybrid deployments**: Mix in-house and client-provided API keys seamlessly

Example mixed configuration:
```bash
# Static API key
# Any client connecting to the proxy will use this API key when connecting to the Poe API provider
POE_API_KEY=your-poe-api-key

# Passthrough API key
# Each client connecting to the proxy will use **their own API key** when connecting to the OpenAI API provider
OPENAI_API_KEY=!PASSTHRU

# Another example with a custom provider
CUSTOM_LLM_API_KEY=!PASSTHRU
CUSTOM_LLM_BASE_URL=https://api.custom-llm.com/v1
```


## How It Works

1. When a provider is configured with `!PASSTHRU`, the proxy will extract the API key from the incoming request headers (`x-api-key` or `Authorization: Bearer <token>`).
2. The extracted client API key is then used to authenticate with the provider identified by the provider prefix in the model name.
3. This enables each client to use their own API key for a given provider.

## Security

- API keys are automatically hashed in logs (first 8 characters of the `SHA256` shown).
- Passthrough providers must receive a valid client API key or will return a 401 error.

## Example Usage

### Provider Configuration
```bash
# .env file
OPENAI_API_KEY=!PASSTHRU
```

### Client Request
```bash
curl -X POST http://localhost:8082/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: my-openai-api-key" \
  -d '{
    "model": "openai:gpt-4o-mini",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

In this example:
- The client provides their OpenAI API key in the `x-api-key` header
- The proxy passes this key directly to the OpenAI API provider
- No static API key is stored on the proxy for OpenAI

## Implementation Approaches

There are different ways to implement API key passthrough in proxies:

### Sentinel-based Approach (Current Implementation)
- **Configuration**: Explicit `!PASSTHRU` sentinel value marks providers for passthrough
- **Granularity**: Per-provider configuration
- **Flexibility**: Supports mixed static and passthrough providers simultaneously
- **Security**: Clear visual indicator of passthrough providers
- **Migration**: Gradual, provider-by-provider transition possible

### Absence-based Approach
- **Configuration**: Presence or absence of server API key determines mode
- **Granularity**: Server-wide mode (all providers behave the same)
- **Flexibility**: All-or-nothing approach
- **Simplicity**: Easier to understand and configure
- **Use Case**: Best for pure multi-tenant deployments

### Header-based Approach
- **Configuration**: Special headers indicate passthrough requirements
- **Granularity**: Per-request mode selection
- **Complexity**: Requires changes to client implementations
- **Flexibility**: Most granular control

### Why Sentinel-based?

The sentinel-based approach was chosen for Vandamme Proxy because it:

1. **Minimizes Security Risks**: Explicit marking prevents accidental passthrough
2. **Maximizes Flexibility**: Supports hybrid deployment scenarios
3. **Maintains Compatibility**: Zero impact on existing configurations and clients
4. **Enables Gradual Migration**: Providers can transition independently
5. **Provides Clear Intent**: Configuration immediately shows passthrough behavior

## Error Handling

If a passthrough provider is configured but the client doesn't provide an API key:
```json
{
  "type": "error",
  "error": {
    "type": "api_error",
    "message": "Provider 'openai' requires API key passthrough, but no client API key was provided"
  }
}
```
